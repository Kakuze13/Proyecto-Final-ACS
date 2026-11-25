import argparse
import asyncio
import logging

from server.socket_server import SocketServer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Servidor TCP concurrente de ChatRoom")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--database", default="chatroom.db")
    return parser.parse_args()


async def run_server(host: str, port: int, database_path: str) -> None:
    server = SocketServer(host, port, database_path)
    await server.start()
    try:
        await server.serve_forever()
    finally:
        await server.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    try:
        asyncio.run(run_server(args.host, args.port, args.database))
    except KeyboardInterrupt:
        logging.info("Apagado solicitado")


if __name__ == "__main__":
    main()
