import asyncio
import json
import socket
from pathlib import Path
from typing import Any

import pytest

from client.tcp_client import TcpClient
from server.socket_server import SocketServer


def create_test_server(tmp_path: Path, **options: Any) -> SocketServer:
    return SocketServer(
        "127.0.0.1",
        0,
        tmp_path / "chatroom.sqlite3",
        **options,
    )


async def send_request(
    writer: asyncio.StreamWriter,
    reader: asyncio.StreamReader,
    message: dict[str, str],
) -> dict[str, object]:
    writer.write(json.dumps(message).encode("utf-8") + b"\n")
    await writer.drain()
    while True:
        response = json.loads(await asyncio.wait_for(reader.readline(), 1))
        if response.get("request_id") == message["request_id"]:
            return response


async def read_event(
    reader: asyncio.StreamReader,
    event_type: str,
) -> dict[str, object]:
    while True:
        event = json.loads(await asyncio.wait_for(reader.readline(), 1))
        if event.get("type") == event_type:
            return event


async def read_response(
    reader: asyncio.StreamReader,
    request_id: str,
) -> dict[str, object]:
    while True:
        response = json.loads(await asyncio.wait_for(reader.readline(), 1))
        if response.get("request_id") == request_id:
            return response


def test_server_handles_two_clients_and_duplicate_usernames(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = create_test_server(tmp_path)
        await server.start()
        port = server.sockets[0].getsockname()[1]
        writers: list[asyncio.StreamWriter] = []
        try:
            first, second = await asyncio.gather(
                asyncio.open_connection("127.0.0.1", port),
                asyncio.open_connection("127.0.0.1", port),
            )
            first_reader, first_writer = first
            second_reader, second_writer = second
            writers.extend((first_writer, second_writer))

            first_connected = await send_request(
                first_writer,
                first_reader,
                {"type": "CONNECT", "request_id": "1", "username": "Ana"},
            )
            assert first_connected["type"] == "SUCCESS"
            second_connected = await send_request(
                second_writer,
                second_reader,
                {"type": "CONNECT", "request_id": "2", "username": "Bob"},
            )
            assert second_connected["type"] == "SUCCESS"

            duplicate, duplicate_writer = await asyncio.open_connection("127.0.0.1", port)
            writers.append(duplicate_writer)
            invalid_name = await send_request(
                duplicate_writer,
                duplicate,
                {"type": "CONNECT", "request_id": "3a", "username": "ab"},
            )
            assert invalid_name["code"] == "INVALID_USERNAME"
            duplicate_result = await send_request(
                duplicate_writer,
                duplicate,
                {"type": "CONNECT", "request_id": "3", "username": "ana"},
            )
            assert duplicate_result["code"] == "USERNAME_TAKEN"

            listed = await send_request(
                first_writer,
                first_reader,
                {"type": "LIST_USERS", "request_id": "4"},
            )
            assert listed["data"] == {"users": ["Ana", "Bob"]}

            first_writer.close()
            await first_writer.wait_closed()
            writers.remove(first_writer)
            still_active = await send_request(
                second_writer,
                second_reader,
                {"type": "LIST_USERS", "request_id": "5"},
            )
            assert still_active["data"] == {"users": ["Bob"]}

            disconnected = await send_request(
                second_writer,
                second_reader,
                {"type": "DISCONNECT", "request_id": "6"},
            )
            assert disconnected["operation"] == "DISCONNECT"
            reconnected = await send_request(
                duplicate_writer,
                duplicate,
                {"type": "CONNECT", "request_id": "7", "username": "Bob"},
            )
            assert reconnected["type"] == "SUCCESS"
        finally:
            for writer in writers:
                writer.close()
            await server.close()

    asyncio.run(scenario())


def test_server_reassembles_fragmented_frames_and_reads_coalesced_frames(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        server = create_test_server(tmp_path)
        await server.start()
        port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        connect_frame = b'{"type":"CONNECT","request_id":"fragment","username":"Alice"}\n'
        list_frame = b'{"type":"LIST_USERS","request_id":"coalesced"}\n'
        try:
            split_at = len(connect_frame) // 2
            writer.write(connect_frame[:split_at])
            await writer.drain()
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(reader.readline(), 0.05)

            writer.write(connect_frame[split_at:] + list_frame)
            await writer.drain()
            response = json.loads(await asyncio.wait_for(reader.readline(), 1))
            event = json.loads(await asyncio.wait_for(reader.readline(), 1))
            listed = json.loads(await asyncio.wait_for(reader.readline(), 1))
            assert response["request_id"] == "fragment"
            assert event["type"] == "USER_CONNECTED"
            assert listed["request_id"] == "coalesced"
            assert listed["data"] == {"users": ["Alice"]}
        finally:
            writer.close()
            await writer.wait_closed()
            await server.close()

    asyncio.run(scenario())


def test_rooms_keep_membership_isolated_and_clean_up_disconnected_users(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = create_test_server(tmp_path)
        await server.start()
        port = server.sockets[0].getsockname()[1]
        connections = await asyncio.gather(
            asyncio.open_connection("127.0.0.1", port),
            asyncio.open_connection("127.0.0.1", port),
        )
        (alice_reader, alice_writer), (bob_reader, bob_writer) = connections
        try:
            for reader, writer, username, request_id in (
                (alice_reader, alice_writer, "Alice", "a1"),
                (bob_reader, bob_writer, "Bob", "b1"),
            ):
                result = await send_request(
                    writer,
                    reader,
                    {"type": "CONNECT", "request_id": request_id, "username": username},
                )
                assert result["type"] == "SUCCESS"

            created = await send_request(
                alice_writer,
                alice_reader,
                {"type": "CREATE_ROOM", "request_id": "a2", "room": "general"},
            )
            assert created["data"] == {"room": "general"}
            joined = await send_request(
                bob_writer,
                bob_reader,
                {"type": "JOIN_ROOM", "request_id": "b2", "room": "general"},
            )
            assert joined["type"] == "SUCCESS"
            members = await send_request(
                alice_writer,
                alice_reader,
                {"type": "LIST_USERS", "request_id": "a3", "room": "general"},
            )
            assert members["data"] == {"users": ["Alice", "Bob"]}

            duplicate = await send_request(
                bob_writer,
                bob_reader,
                {"type": "JOIN_ROOM", "request_id": "b3", "room": "general"},
            )
            assert duplicate["code"] == "ALREADY_IN_ROOM"
            bob_writer.close()
            await bob_writer.wait_closed()
            members_after_disconnect = await send_request(
                alice_writer,
                alice_reader,
                {"type": "LIST_USERS", "request_id": "a4", "room": "general"},
            )
            assert members_after_disconnect["data"] == {"users": ["Alice"]}
        finally:
            alice_writer.close()
            await alice_writer.wait_closed()
            await server.close()

    asyncio.run(scenario())


def test_messages_are_limited_to_room_members_and_use_session_identity(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = create_test_server(tmp_path)
        await server.start()
        port = server.sockets[0].getsockname()[1]
        connections = await asyncio.gather(
            *(asyncio.open_connection("127.0.0.1", port) for _ in range(3))
        )
        readers = [connection[0] for connection in connections]
        writers = [connection[1] for connection in connections]
        try:
            for index, username in enumerate(("Alice", "Bob", "Cora")):
                assert (
                    await send_request(
                        writers[index],
                        readers[index],
                        {"type": "CONNECT", "request_id": f"c{index}", "username": username},
                    )
                )["type"] == "SUCCESS"
            await send_request(
                writers[0],
                readers[0],
                {"type": "CREATE_ROOM", "request_id": "r1", "room": "general"},
            )
            await send_request(
                writers[1],
                readers[1],
                {"type": "JOIN_ROOM", "request_id": "r2", "room": "general"},
            )
            await send_request(
                writers[2],
                readers[2],
                {"type": "CREATE_ROOM", "request_id": "r3", "room": "private"},
            )

            rejected = await send_request(
                writers[2],
                readers[2],
                {"type": "SEND_MESSAGE", "request_id": "m0", "room": "general", "content": "hola"},
            )
            assert rejected["code"] == "NOT_IN_ROOM"
            empty = await send_request(
                writers[0],
                readers[0],
                {"type": "SEND_MESSAGE", "request_id": "m1", "room": "general", "content": ""},
            )
            assert empty["code"] == "INVALID_CONTENT"
            invalid_unicode = await send_request(
                writers[0],
                readers[0],
                {
                    "type": "SEND_MESSAGE",
                    "request_id": "m2",
                    "room": "general",
                    "content": "\ud800",
                },
            )
            assert invalid_unicode["code"] == "INVALID_CONTENT"

            writers[0].write(
                b'{"type":"SEND_MESSAGE","request_id":"m3","room":"general",'
                b'"content":"hola"}\n'
            )
            await writers[0].drain()
            events = await asyncio.gather(
                *(read_event(readers[index], "CHAT_MESSAGE") for index in (0, 1))
            )
            assert all(event["type"] == "CHAT_MESSAGE" for event in events)
            assert all(event["username"] == "Alice" for event in events)
            assert all(event["content"] == "hola" for event in events)
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(readers[2].readline(), 0.05)

            writers[2].write(
                b'{"type":"SEND_MESSAGE","request_id":"m4","room":"general",'
                b'"content":"hola","username":"Cora"}\n'
            )
            await writers[2].drain()
            result = json.loads(await asyncio.wait_for(readers[2].readline(), 1))
            assert result["code"] == "INVALID_REQUEST"
            listed = await send_request(
                writers[2],
                readers[2],
                {"type": "LIST_USERS", "request_id": "m5"},
            )
            assert listed["type"] == "SUCCESS"
        finally:
            for writer in writers:
                writer.close()
            await server.close()

    asyncio.run(scenario())


def test_events_reach_only_the_defined_recipients(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = create_test_server(tmp_path)
        await server.start()
        port = server.sockets[0].getsockname()[1]
        (alice_reader, alice_writer), (bob_reader, bob_writer) = await asyncio.gather(
            asyncio.open_connection("127.0.0.1", port),
            asyncio.open_connection("127.0.0.1", port),
        )
        try:
            await send_request(
                alice_writer,
                alice_reader,
                {"type": "CONNECT", "request_id": "a1", "username": "Alice"},
            )
            assert (await read_event(alice_reader, "USER_CONNECTED"))["username"] == "Alice"

            await send_request(
                bob_writer,
                bob_reader,
                {"type": "CONNECT", "request_id": "b1", "username": "Bob"},
            )
            alice_connected = await read_event(alice_reader, "USER_CONNECTED")
            bob_connected = await read_event(bob_reader, "USER_CONNECTED")
            assert alice_connected["username"] == bob_connected["username"] == "Bob"

            alice_writer.write(
                b'{"type":"CREATE_ROOM","request_id":"a2","room":"general"}\n'
            )
            await alice_writer.drain()
            room_events = await asyncio.gather(
                read_event(alice_reader, "ROOM_CREATED"),
                read_event(bob_reader, "ROOM_CREATED"),
            )
            assert all(event["room"] == "general" for event in room_events)
            assert (await read_response(alice_reader, "a2"))["type"] == "SUCCESS"

            await send_request(
                bob_writer,
                bob_reader,
                {"type": "JOIN_ROOM", "request_id": "b2", "room": "general"},
            )
            joined = await read_event(alice_reader, "USER_JOINED")
            assert joined["username"] == "Bob"
            await send_request(
                bob_writer,
                bob_reader,
                {"type": "LEAVE_ROOM", "request_id": "b3", "room": "general"},
            )
            left = await read_event(alice_reader, "USER_LEFT")
            assert left["username"] == "Bob"

            alice_writer.close()
            await alice_writer.wait_closed()
            disconnected = await read_event(bob_reader, "USER_DISCONNECTED")
            assert disconnected["username"] == "Alice"
        finally:
            bob_writer.close()
            await server.close()

    asyncio.run(scenario())


def test_saturated_client_is_closed_without_blocking_healthy_members(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = create_test_server(
            tmp_path,
            queue_size=1,
            enqueue_timeout=0.01,
        )
        await server.start()
        port = server.sockets[0].getsockname()[1]
        alice = TcpClient()
        healthy = TcpClient()
        slow_reader, slow_writer = await asyncio.open_connection(
            "127.0.0.1",
            port,
            limit=1_024,
        )
        try:
            await asyncio.gather(
                alice.connect("127.0.0.1", port),
                healthy.connect("127.0.0.1", port),
            )
            await alice.request(
                {"type": "CONNECT", "request_id": "c1", "username": "Alice"}
            )
            await send_request(
                slow_writer,
                slow_reader,
                {"type": "CONNECT", "request_id": "c2", "username": "Slow"},
            )
            await healthy.request(
                {"type": "CONNECT", "request_id": "c3", "username": "Healthy"}
            )
            await alice.request(
                {"type": "CREATE_ROOM", "request_id": "r1", "room": "general"}
            )
            await send_request(
                slow_writer,
                slow_reader,
                {"type": "JOIN_ROOM", "request_id": "r2", "room": "general"},
            )
            await healthy.request(
                {"type": "JOIN_ROOM", "request_id": "r3", "room": "general"}
            )

            sessions = await server._connections.sessions()
            slow_session = None
            for session in sessions:
                user = await server._connections.user_for(session)
                if user is not None and user.username == "Slow":
                    slow_session = session
                    break
            assert slow_session is not None
            slow_socket = slow_session.writer.get_extra_info("socket")
            slow_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024)

            message_count = 100
            for index in range(message_count):
                result = await alice.request(
                    {
                        "type": "SEND_MESSAGE",
                        "request_id": f"m{index}",
                        "room": "general",
                        "content": "x" * 2_000,
                    },
                )
                assert result["type"] == "SUCCESS"

            async def collect_messages() -> int:
                received = 0
                while received < message_count:
                    event = await asyncio.wait_for(healthy.events.get(), 5)
                    if event.get("type") == "CHAT_MESSAGE":
                        received += 1
                return received

            assert await collect_messages() == message_count

            while await asyncio.wait_for(slow_reader.read(4096), 1):
                pass
        finally:
            slow_writer.close()
            await slow_writer.wait_closed()
            await alice.close()
            await healthy.close()
            await server.close()

    asyncio.run(scenario())


def test_rooms_and_message_history_survive_server_restart(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = create_test_server(tmp_path)
        await server.start()
        port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        try:
            await send_request(
                writer,
                reader,
                {"type": "CONNECT", "request_id": "c1", "username": "Alice"},
            )
            await send_request(
                writer,
                reader,
                {"type": "CREATE_ROOM", "request_id": "r1", "room": "persisted"},
            )
            await send_request(
                writer,
                reader,
                {
                    "type": "SEND_MESSAGE",
                    "request_id": "m1",
                    "room": "persisted",
                    "content": "kept after restart",
                },
            )
        finally:
            writer.close()
            await writer.wait_closed()
            await server.close()

        restarted = create_test_server(tmp_path)
        await restarted.start()
        restarted_port = restarted.sockets[0].getsockname()[1]
        new_reader, new_writer = await asyncio.open_connection(
            "127.0.0.1", restarted_port
        )
        try:
            await send_request(
                new_writer,
                new_reader,
                {"type": "CONNECT", "request_id": "c2", "username": "Bob"},
            )
            rooms = await send_request(
                new_writer,
                new_reader,
                {"type": "LIST_ROOMS", "request_id": "r2"},
            )
            assert rooms["data"]["rooms"] == [{"room": "persisted", "members_count": 0}]
            await send_request(
                new_writer,
                new_reader,
                {"type": "JOIN_ROOM", "request_id": "j1", "room": "persisted"},
            )
            history = await send_request(
                new_writer,
                new_reader,
                {"type": "HISTORY", "request_id": "h1", "room": "persisted"},
            )
            assert history["type"] == "HISTORY_RESULT"
            assert history["messages"][0]["content"] == "kept after restart"
            assert history["messages"][0]["username"] == "Alice"
        finally:
            new_writer.close()
            await new_writer.wait_closed()
            await restarted.close()

    asyncio.run(scenario())


def test_large_history_is_truncated_to_a_valid_protocol_frame(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = create_test_server(tmp_path)
        await server.start()
        port = server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        try:
            await send_request(
                writer,
                reader,
                {"type": "CONNECT", "request_id": "c1", "username": "Alice"},
            )
            await send_request(
                writer,
                reader,
                {"type": "CREATE_ROOM", "request_id": "r1", "room": "large"},
            )
            for index in range(10):
                await send_request(
                    writer,
                    reader,
                    {
                        "type": "SEND_MESSAGE",
                        "request_id": f"m{index}",
                        "room": "large",
                        "content": f"{index}:" + "😀" * 1_998,
                    },
                )
            history = await send_request(
                writer,
                reader,
                {
                    "type": "HISTORY",
                    "request_id": "h1",
                    "room": "large",
                    "limit": 100,
                },
            )
            assert history["type"] == "HISTORY_RESULT"
            assert history["truncated"] is True
            assert len(history["messages"]) < 10
            assert history["messages"][-1]["content"].startswith("9:")
        finally:
            writer.close()
            await writer.wait_closed()
            await server.close()

    asyncio.run(scenario())


def test_invalid_and_oversized_frames_receive_error_then_close(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = create_test_server(tmp_path)
        await server.start()
        port = server.sockets[0].getsockname()[1]
        try:
            for payload in (b"{bad json}\n", b"x" * 65_537 + b"\n"):
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.write(payload)
                await writer.drain()
                response = json.loads(await asyncio.wait_for(reader.readline(), 1))
                assert response["type"] == "ERROR"
                assert response["request_id"] is None
                assert response["code"] == (
                    "INVALID_REQUEST" if payload == b"{bad json}\n" else "MESSAGE_TOO_LARGE"
                )
                assert await asyncio.wait_for(reader.read(), 1) == b""
                writer.close()
                await writer.wait_closed()
        finally:
            await server.close()

    asyncio.run(scenario())


def test_idle_timeout_and_connection_limit_are_enforced(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = create_test_server(tmp_path, max_connections=1, read_timeout=0.15)
        await server.start()
        port = server.sockets[0].getsockname()[1]
        first_reader, first_writer = await asyncio.open_connection("127.0.0.1", port)
        second_writer = None
        try:
            connected = await send_request(
                first_writer,
                first_reader,
                {"type": "CONNECT", "request_id": "c1", "username": "Alice"},
            )
            assert connected["type"] == "SUCCESS"
            assert (await read_event(first_reader, "USER_CONNECTED"))["username"] == "Alice"
            second_reader, second_writer = await asyncio.open_connection(
                "127.0.0.1", port
            )
            assert await asyncio.wait_for(second_reader.read(), 1) == b""
            assert await asyncio.wait_for(first_reader.read(), 1) == b""
        finally:
            first_writer.close()
            if second_writer is not None:
                second_writer.close()
            await server.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("client_count", [5, 10, 20, 50])
def test_concurrent_clients_exchange_messages(client_count: int, tmp_path: Path) -> None:
    async def scenario() -> None:
        server = create_test_server(tmp_path)
        await server.start()
        port = server.sockets[0].getsockname()[1]
        clients = [TcpClient() for _ in range(client_count)]
        try:
            await asyncio.gather(
                *(client.connect("127.0.0.1", port) for client in clients)
            )
            await asyncio.gather(
                *(
                    client.request(
                        {
                            "type": "CONNECT",
                            "request_id": f"connect-{index}",
                            "username": f"user_{index}",
                        }
                    )
                    for index, client in enumerate(clients)
                )
            )
            await clients[0].request(
                {"type": "CREATE_ROOM", "request_id": "create-room", "room": "load"}
            )
            await asyncio.gather(
                *(
                    client.request(
                        {
                            "type": "JOIN_ROOM",
                            "request_id": f"join-{index}",
                            "room": "load",
                        }
                    )
                    for index, client in enumerate(clients[1:], start=1)
                )
            )
            await asyncio.gather(
                *(
                    client.request(
                        {
                            "type": "SEND_MESSAGE",
                            "request_id": f"message-{index}",
                            "room": "load",
                            "content": f"from-{index}",
                        }
                    )
                    for index, client in enumerate(clients)
                )
            )

            async def collect_messages(client: TcpClient) -> set[str]:
                usernames = set()
                while len(usernames) < client_count:
                    event = await asyncio.wait_for(client.events.get(), 5)
                    if event.get("type") == "CHAT_MESSAGE":
                        usernames.add(event["username"])
                return usernames

            received = await asyncio.gather(
                *(collect_messages(client) for client in clients)
            )
            expected = {f"user_{index}" for index in range(client_count)}
            assert all(usernames == expected for usernames in received)
        finally:
            await asyncio.gather(*(client.close() for client in clients))
            await server.close()

    asyncio.run(scenario())
