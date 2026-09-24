"""Independent OSC receiver for testing the Max handoff; no Max dependency."""
import argparse
import time
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=9000)
    args = p.parse_args()
    dispatcher = Dispatcher()
    last = [0.0]

    def show(address, *values):
        if address == "/mcns/activity":
            now = time.monotonic()
            if now - last[0] < 1:
                return
            last[0] = now
        elif address not in ("/mcns/state", "/mcns/population"):
            return
        print(address, *values, flush=True)

    dispatcher.set_default_handler(show)
    server = BlockingOSCUDPServer((args.host, args.port), dispatcher)
    print(f"Listening on {args.host}:{args.port}; Ctrl-C to stop", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
