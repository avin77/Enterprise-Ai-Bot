import base64
import os
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security.rate_limit import limiter


class Phase0RoundtripE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["API_TOKEN"] = "dev-token"
        os.environ["RATE_LIMIT_REQUESTS"] = "30"
        os.environ["RATE_LIMIT_WINDOW_SECONDS"] = "60"
        os.environ["USE_AWS_MOCKS"] = "true"
        limiter.reset()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()

    def test_frontend_targets_backend_ws_and_chat_only(self) -> None:
        api_client = Path("frontend/api_client.js").read_text(encoding="utf-8")
        self.assertIn("/chat", api_client)
        self.assertIn("/ws", api_client)

    def test_frontend_contains_no_direct_aws_calls_or_credentials(self) -> None:
        content = (
            Path("frontend/app.js").read_text(encoding="utf-8")
            + Path("frontend/api_client.js").read_text(encoding="utf-8")
            + Path("frontend/index.html").read_text(encoding="utf-8")
        ).lower()
        for blocked in ["aws-sdk", "bedrock", "transcribe", "polly", "akia"]:
            self.assertNotIn(blocked, content)

    def test_chat_roundtrip_uses_backend_endpoint(self) -> None:
        response = self.client.post(
            "/chat",
            json={"text": "status check"},
            headers={"Authorization": "Bearer dev-token"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["reply"], "assistant:status check")

    def test_ws_audio_roundtrip_returns_pipeline_events(self) -> None:
        audio_base64 = base64.b64encode(b"hello").decode("utf-8")
        with self.client.websocket_connect("/ws?token=dev-token") as websocket:
            websocket.receive_json()  # ack
            websocket.send_json({"type": "audio_chunk", "audio_base64": audio_base64})
            partial = websocket.receive_json()
            bot_text = websocket.receive_json()
            bot_audio = websocket.receive_json()
            self.assertEqual(partial["type"], "partial_text")
            self.assertTrue(partial["text"].startswith("transcript:"))
            self.assertEqual(bot_text["type"], "bot_text")
            self.assertTrue(bot_text["text"].startswith("assistant:"))
            self.assertEqual(bot_audio["type"], "bot_audio_chunk")
            self.assertTrue(len(bot_audio["audio_base64"]) > 0)


if __name__ == "__main__":
    unittest.main()

