import argparse
import asyncio
import logging
import sys
import webbrowser

from .adrastea_client import AdrasteaClient
from .buffer import SpeechBuffer
from .config import config
from .server import start_server
from .tts import LocalTTSEngine

logger = logging.getLogger("SpeechFlow.CLI")


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    )


async def cmd_serve(port: int, host: str, open_browser: bool):
    """Launch Speech Flow Web Server and visual conversational interface."""
    await start_server(host=host, port=port)
    url = f"http://127.0.0.1:{port}"
    print(f"\n==================================================")
    print(f"   SPEECH FLOW IS ONLINE")
    print(f"   Local Cockpit:    {url}")
    print(f"   Tailscale Mobile: http://100.112.85.87:{port}")
    print(f"   Adrastea Target:  {config.adrastea_host}:{config.adrastea_port}")
    print(f"==================================================\n")

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    # Run forever
    try:
        while True:
            await asyncio.sleep(3600)
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\nStopping Speech Flow...")


async def cmd_test(text: str = "Adrastea, what is your current system status?"):
    """Verify Adrastea IPC conversation roundtrip and TTS audio output."""
    print(f"Testing Adrastea connection at {config.adrastea_host}:{config.adrastea_port}...")
    client = AdrasteaClient()
    connected = await client.connect()
    if not connected:
        print(f"FAILED: Could not connect to Adrastea IPC at {config.adrastea_host}:{config.adrastea_port}.")
        print("Ensure Adrastea is running: python -m adrastea.cli keepalive")
        sys.exit(1)

    print(f"Transmitting speech buffer: '{text}'")
    resp = await client.send_conversation(text)
    if resp:
        reply = resp.get("text", "No speech reply received.")
        action = resp.get("action", "none")
        print(f"\n[ADRASTEA DECISION & RESPONSE]")
        print(f"Action Taken: {action}")
        print(f"Spoken Voice: {reply}")
        print(f"System State: {resp.get('system_status')}\n")

        print("Playing response aloud through local TTS...")
        tts = LocalTTSEngine()
        tts.speak(reply, block=True)
        print("TTS playback completed.")
    else:
        print("FAILED: Adrastea did not respond to speech buffer.")

    await client.disconnect()


async def cmd_ping():
    """Ping Adrastea over IPC."""
    client = AdrasteaClient()
    connected = await client.connect()
    if not connected:
        print(f"Adrastea is OFFLINE at {config.adrastea_host}:{config.adrastea_port}")
        return
    res = await client.ping_adrastea()
    if res:
        print(f"Adrastea is ALIVE: {res}")
    else:
        print("Ping failed.")
    await client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Speech Flow: Conversational Voice Interface for Adrastea")
    parser.add_argument("command", choices=["serve", "test", "ping"], default="serve", nargs="?")
    parser.add_argument("--port", type=int, default=config.web_port, help="Port to bind web visualizer")
    parser.add_argument("--host", default=config.web_host, help="Host to bind web visualizer")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    parser.add_argument("--text", default="Adrastea, report system status.", help="Text to test conversation roundtrip")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")
    args = parser.parse_args()

    setup_logging(args.verbose)

    if args.command == "serve":
        asyncio.run(cmd_serve(port=args.port, host=args.host, open_browser=not args.no_browser))
    elif args.command == "test":
        asyncio.run(cmd_test(args.text))
    elif args.command == "ping":
        asyncio.run(cmd_ping())


if __name__ == "__main__":
    main()
