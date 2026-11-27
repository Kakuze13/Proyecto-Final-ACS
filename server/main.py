import argparse
import asyncio
import logging
import signal

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
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    installed_signals: list[signal.Signals] = []
    for shutdown_signal in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(shutdown_signal, stop.set)
            installed_signals.append(shutdown_signal)
        except (NotImplementedError, RuntimeError, ValueError):
            # Windows event loops may not support add_signal_handler.
            continue
    try:
        await stop.wait()
    finally:
        await server.close()
        for shutdown_signal in installed_signals:
            loop.remove_signal_handler(shutdown_signal)


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
