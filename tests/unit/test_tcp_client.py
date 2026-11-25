import asyncio
import json

from client.tcp_client import TcpClient


def test_tcp_client_routes_response_and_unsolicited_event() -> None:
    async def scenario() -> None:
        async def handler(
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
        ) -> None:
            request = json.loads(await reader.readline())
            writer.write(
                b'{"type":"USER_CONNECTED","username":"Bob"}\n'
                + json.dumps(
                    {
                        "type": "SUCCESS",
                        "request_id": request["request_id"],
                        "operation": "LIST_ROOMS",
                    }
                ).encode("utf-8")
                + b"\n"
            )
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        client = TcpClient()
        try:
            await client.connect("127.0.0.1", port)
            result = await client.request(
                {"type": "LIST_ROOMS", "request_id": "request-1"}
            )
            event = await asyncio.wait_for(client.events.get(), 1)
            assert result["type"] == "SUCCESS"
            assert event == {"type": "USER_CONNECTED", "username": "Bob"}
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())
