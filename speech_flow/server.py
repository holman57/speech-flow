import asyncio
import json
import logging
from pathlib import Path
from typing import Set

import tornado.ioloop
import tornado.web
import tornado.websocket

from .adrastea_client import AdrasteaClient
from .buffer import SpeechBuffer
from .config import config
from .tts import LocalTTSEngine

logger = logging.getLogger("SpeechFlow.Server")


class SpeechFlowState:
    """Shared application state managing the speech buffer, Adrastea client, and active clients."""

    def __init__(self):
        self.buffer = SpeechBuffer(max_words=config.max_buffer_words, silence_timeout=config.silence_threshold_seconds)
        self.adrastea = AdrasteaClient(host=config.adrastea_host, port=config.adrastea_port)
        self.tts = LocalTTSEngine(rate=config.tts_rate)
        self.ws_clients: Set["SpeechWebSocketHandler"] = set()
        self.conversation_history = []

    async def initialize(self):
        connected = await self.adrastea.connect()
        logger.info(f"Adrastea IPC connectivity status: {'CONNECTED' if connected else 'OFFLINE (will retry on demand)'}")

    def broadcast(self, message: dict):
        data = json.dumps(message)
        for client in list(self.ws_clients):
            try:
                client.write_message(data)
            except Exception:
                pass


state = SpeechFlowState()


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")


class StatusAPIHandler(tornado.web.RequestHandler):
    async def get(self):
        adrastea_alive = await state.adrastea.is_connected()
        ping_res = await state.adrastea.ping_adrastea() if adrastea_alive else None
        self.write({
            "status": "online",
            "adrastea_connected": adrastea_alive,
            "adrastea_status": ping_res,
            "buffer_metrics": state.buffer.get_metrics(),
            "history_count": len(state.conversation_history)
        })


class CommandAPIHandler(tornado.web.RequestHandler):
    async def post(self):
        try:
            data = json.loads(self.request.body.decode("utf-8"))
            text = data.get("text", "").strip()
            if not text:
                self.set_status(400)
                self.write({"error": "Empty text payload"})
                return

            response = await state.adrastea.send_conversation(text)
            reply_text = response.get("text", "Adrastea did not return a voice response.") if response else "Adrastea offline."
            action = response.get("action", "none") if response else "error"

            # Record in conversation history
            entry = {
                "user": text,
                "adrastea": reply_text,
                "action": action,
                "status": response.get("system_status", {}) if response else {}
            }
            state.conversation_history.append(entry)

            # Local TTS playback
            if config.tts_enabled:
                state.tts.speak(reply_text)

            # Broadcast update
            state.broadcast({"type": "conversation_entry", "entry": entry})
            self.write(entry)
        except Exception as e:
            self.set_status(500)
            self.write({"error": str(e)})


class SpeechWebSocketHandler(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        state.ws_clients.add(self)
        logger.info("Speech Flow client connected to WebSocket.")
        # Send initial buffer state & history
        self.write_message(json.dumps({
            "type": "init",
            "buffer": state.buffer.to_dict(),
            "history": state.conversation_history[-20:]
        }))

    def on_close(self):
        state.ws_clients.discard(self)
        logger.info("Speech Flow client disconnected from WebSocket.")

    async def on_message(self, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "interim_speech":
                # Real-time interim speech update
                text = data.get("text", "")
                state.buffer.update_interim(text)
                state.broadcast({
                    "type": "buffer_update",
                    "buffer": state.buffer.to_dict()
                })

            elif msg_type == "final_speech":
                # Finalized phrase from speech recognition
                phrase = data.get("text", "")
                confidence = float(data.get("confidence", 1.0))
                state.buffer.append_final_phrase(phrase, confidence=confidence)
                state.broadcast({
                    "type": "buffer_update",
                    "buffer": state.buffer.to_dict()
                })

            elif msg_type == "dispatch_buffer":
                # Send the accumulated buffer to Adrastea
                full_text = state.buffer.get_full_text()
                word_list = state.buffer.get_word_list()
                if not full_text:
                    return

                logger.info(f"Dispatching speech buffer to Adrastea: '{full_text}'")
                state.broadcast({
                    "type": "adrastea_thinking",
                    "prompt": full_text
                })

                # Clear speech buffer immediately as it is now dispatched
                state.buffer.clear()
                state.broadcast({
                    "type": "buffer_update",
                    "buffer": state.buffer.to_dict()
                })

                # Query Adrastea
                resp = await state.adrastea.send_conversation(full_text, word_list=word_list)
                reply_text = resp.get("text", "Adrastea processed your request.") if resp else "Adrastea is currently unreachable via IPC."
                action_taken = resp.get("action", "none") if resp else "error"

                entry = {
                    "user": full_text,
                    "adrastea": reply_text,
                    "action": action_taken,
                    "status": resp.get("system_status", {}) if resp else {}
                }
                state.conversation_history.append(entry)

                # Local desktop TTS playback
                if config.tts_enabled:
                    state.tts.speak(reply_text)

                # Broadcast response to frontend (frontend will also play browser speech synthesis)
                state.broadcast({
                    "type": "adrastea_response",
                    "entry": entry
                })

            elif msg_type == "clear_buffer":
                state.buffer.clear()
                state.broadcast({
                    "type": "buffer_update",
                    "buffer": state.buffer.to_dict()
                })

            elif msg_type == "ping_adrastea":
                status = await state.adrastea.ping_adrastea()
                self.write_message(json.dumps({
                    "type": "adrastea_status",
                    "status": status
                }))

        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}", exc_info=True)


def make_app():
    static_path = Path(__file__).resolve().parent / "static"
    settings = {
        "template_path": static_path,
        "static_path": static_path,
        "debug": False,
    }
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/ws", SpeechWebSocketHandler),
        (r"/api/status", StatusAPIHandler),
        (r"/api/command", CommandAPIHandler),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": static_path}),
    ], **settings)


async def start_server(host: str = config.web_host, port: int = config.web_port):
    """Start Speech Flow web and websocket server."""
    app = make_app()
    app.listen(port, address=host)
    await state.initialize()
    logger.info("==================================================")
    logger.info("   SPEECH FLOW: CONVERSATIONAL VOICE INTERFACE")
    logger.info(f"   Listening on: http://{host}:{port}")
    logger.info(f"   Connecting to Adrastea IPC: {config.adrastea_host}:{config.adrastea_port}")
    logger.info("==================================================")
