import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional
from .config import config

logger = logging.getLogger("SpeechFlow.AdrasteaClient")


class AdrasteaClient:
    """Interfaces Speech Flow directly with Adrastea's dual-engine architecture via IPC."""

    def __init__(self, host: str = config.adrastea_host, port: int = config.adrastea_port):
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._running = False
        self._listen_task: Optional[asyncio.Task] = None
        self._pending_queries: Dict[str, asyncio.Future] = {}

    async def connect(self, retries: int = 3, delay: float = 0.5) -> bool:
        """Establish asynchronous socket connection to Adrastea IPC."""
        for attempt in range(retries):
            try:
                self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
                self._running = True
                self._listen_task = asyncio.create_task(self._listen_loop())
                logger.info(f"Connected to Adrastea IPC Server at {self.host}:{self.port}")
                return True
            except Exception as e:
                logger.debug(f"IPC connection attempt {attempt + 1}/{retries} failed: {e}")
                await asyncio.sleep(delay)
        logger.warning(f"Could not connect to Adrastea IPC at {self.host}:{self.port}.")
        return False

    async def disconnect(self) -> None:
        """Gracefully disconnect from Adrastea."""
        self._running = False
        if self._listen_task:
            self._listen_task.cancel()
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
        for fut in list(self._pending_queries.values()):
            if not fut.done():
                fut.cancel()
        self._pending_queries.clear()
        logger.info("Disconnected from Adrastea IPC.")

    async def is_connected(self) -> bool:
        """Verify if client is currently connected and active."""
        return self._running and self.writer is not None and not self.writer.is_closing()

    async def send_message(self, signal: str, payload: Dict[str, Any]) -> Optional[str]:
        """Send a JSON message over the wire and return message_id."""
        if not await self.is_connected():
            connected = await self.connect()
            if not connected:
                return None

        msg_id = str(uuid.uuid4())[:8]
        msg = {
            "signal": signal,
            "sender": "SpeechFlow",
            "payload": payload,
            "message_id": msg_id,
            "timestamp": time.time()
        }

        try:
            line = json.dumps(msg) + "\n"
            self.writer.write(line.encode("utf-8"))
            await self.writer.drain()
            return msg_id
        except Exception as e:
            logger.error(f"Failed to send IPC message to Adrastea: {e}")
            return None

    async def query(self, signal: str, payload: Dict[str, Any], timeout: float = 15.0) -> Optional[Dict[str, Any]]:
        """Send a request to Adrastea and await its decision and response."""
        if not await self.is_connected():
            connected = await self.connect()
            if not connected:
                return None

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()

        msg_id = str(uuid.uuid4())[:8]
        self._pending_queries[msg_id] = future

        msg = {
            "signal": signal,
            "sender": "SpeechFlow",
            "payload": payload,
            "message_id": msg_id,
            "timestamp": time.time()
        }

        try:
            line = json.dumps(msg) + "\n"
            self.writer.write(line.encode("utf-8"))
            await self.writer.drain()
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Query {signal} (ID: {msg_id}) to Adrastea timed out after {timeout}s.")
            return None
        except Exception as e:
            logger.error(f"Error querying Adrastea: {e}")
            return None
        finally:
            self._pending_queries.pop(msg_id, None)

    async def send_conversation(self, text: str, word_list: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Send transcribed speech buffer to Adrastea for cognitive decision and speech response."""
        payload = {
            "text": text,
            "words": word_list or text.split(),
            "timestamp": time.time()
        }
        resp = await self.query("SIG_CONVERSATION", payload, timeout=20.0)
        return resp.get("payload", {}) if resp else None

    async def ping_adrastea(self) -> Optional[Dict[str, Any]]:
        """Ping Adrastea with SIG_HEARTBEAT to check health and sleep state."""
        resp = await self.query("SIG_HEARTBEAT", {"action": "ping"}, timeout=3.0)
        return resp.get("payload", {}) if resp else None

    async def _listen_loop(self) -> None:
        """Background reader for incoming responses and telemetry from Adrastea."""
        buffer = ""
        try:
            while self._running and self.reader:
                data = await self.reader.read(4096)
                if not data:
                    break
                buffer += data.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        try:
                            msg = json.loads(line.strip())
                            reply_to = msg.get("payload", {}).get("reply_to")
                            # Match pending query strictly by reply_to
                            if reply_to and reply_to in self._pending_queries:
                                fut = self._pending_queries.pop(reply_to)
                                if not fut.done():
                                    fut.set_result(msg)
                        except Exception as e:
                            logger.error(f"Error parsing incoming Adrastea message: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Adrastea listener error: {e}")
        finally:
            self._running = False
