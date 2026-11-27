import argparse
import asyncio
import logging

from server.socket_server import SocketServer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Servidor TCP concurrente de ChatRoom")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--database", default="chatroom.db")
    parser.add_argument("--queue-size", type=int, default=100)
    parser.add_argument("--enqueue-timeout", type=float, default=0.1)
    parser.add_argument("--socket-send-buffer", type=int)
    return parser.parse_args()


async def run_server(
    host: str,
    port: int,
    database_path: str,
    queue_size: int = 100,
    enqueue_timeout: float = 0.1,
    socket_send_buffer: int | None = None,
) -> None:
    server = SocketServer(
        host,
        port,
        database_path,
        queue_size=queue_size,
        enqueue_timeout=enqueue_timeout,
        socket_send_buffer=socket_send_buffer,
    )
    await server.start()
    try:
        await server.serve_forever()
    finally:
        await server.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    try:
        asyncio.run(
            run_server(
                args.host,
                args.port,
                args.database,
                args.queue_size,
                args.enqueue_timeout,
                args.socket_send_buffer,
            )
        )
    except KeyboardInterrupt:
        logging.info("Apagado solicitado")


if __name__ == "__main__":
    main()
