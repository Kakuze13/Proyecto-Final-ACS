import argparse
import asyncio

from client.command_handler import run_console


def main() -> None:
    parser = argparse.ArgumentParser(description="Cliente de consola ChatRoom")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    asyncio.run(run_console(args.host, args.port))


if __name__ == "__main__":
    main()
