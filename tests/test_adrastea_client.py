import asyncio
import sys
import unittest
from pathlib import Path

# Add Adrastea to sys.path for end-to-end integration test
adrastea_dir = Path("C:/Users/LukeH/Adrastea")
if str(adrastea_dir) not in sys.path:
    sys.path.insert(0, str(adrastea_dir))

from adrastea.alpha.engine import AlphaEngine
from speech_flow.adrastea_client import AdrasteaClient


class TestAdrasteaClient(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_port = 9250
        self.alpha = AlphaEngine()
        self.alpha.ipc.port = self.test_port
        self.alpha.spawner.port = self.test_port
        await self.alpha.ipc.start()

        self.client = AdrasteaClient(host="127.0.0.1", port=self.test_port)

    async def asyncTearDown(self):
        await self.client.disconnect()
        await self.alpha.ipc.stop()

    async def test_ping_roundtrip(self):
        connected = await self.client.connect()
        self.assertTrue(connected)

        res = await self.client.ping_adrastea()
        self.assertIsNotNone(res)
        self.assertEqual(res.get("status"), "alive")

    async def test_status_conversation_roundtrip(self):
        connected = await self.client.connect()
        self.assertTrue(connected)

        # Send speech input asking for status
        resp = await self.client.send_conversation("Adrastea, what is your current system status?")
        self.assertIsNotNone(resp)
        self.assertEqual(resp.get("action"), "status_report")
        self.assertIn("Adrastea is currently", resp.get("text", ""))

    async def test_wake_conversation_roundtrip(self):
        connected = await self.client.connect()
        self.assertTrue(connected)

        # Put Alpha to sleep
        await self.alpha.sleep(duration=600.0)
        self.assertTrue(self.alpha._sleeping)

        # Send speech input asking to wake up
        resp = await self.client.send_conversation("Adrastea, wake up and start working.")
        self.assertIsNotNone(resp)
        self.assertEqual(resp.get("action"), "system_wake")
        self.assertFalse(self.alpha._sleeping)
        self.assertIn("awakened", resp.get("text", "").lower())


if __name__ == "__main__":
    unittest.main()
