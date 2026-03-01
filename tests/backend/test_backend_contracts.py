import os
import unittest

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security.rate_limit import limiter

VALID_TOKEN = "dev-token"


class BackendContractTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["API_TOKEN"] = VALID_TOKEN
        os.environ["RATE_LIMIT_REQUESTS"] = "2"
        os.environ["RATE_LIMIT_WINDOW_SECONDS"] = "60"
        limiter.reset()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()

    def test_health_endpoint_exists(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_chat_rejects_missing_token(self) -> None:
        response = self.client.post("/chat", json={"text": "hello"})
        self.assertEqual(response.status_code, 401)

    def test_chat_rejects_invalid_token(self) -> None:
        response = self.client.post(
            "/chat",
            json={"text": "hello"},
            headers={"Authorization": "Bearer invalid"},
        )
        self.assertEqual(response.status_code, 401)

    def test_chat_accepts_valid_token(self) -> None:
        response = self.client.post(
            "/chat",
            json={"text": "hello"},
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reply"], "echo: hello")

    def test_chat_rate_limit_enforced(self) -> None:
        headers = {"Authorization": f"Bearer {VALID_TOKEN}"}
        self.assertEqual(
            self.client.post("/chat", json={"text": "one"}, headers=headers).status_code,
            200,
        )
        self.assertEqual(
            self.client.post("/chat", json={"text": "two"}, headers=headers).status_code,
            200,
        )
        limited = self.client.post("/chat", json={"text": "three"}, headers=headers)
        self.assertEqual(limited.status_code, 429)

    def test_ws_rejects_missing_token(self) -> None:
        with self.assertRaises(Exception):
            with self.client.websocket_connect("/ws"):
                pass

    def test_ws_accepts_valid_token_and_echoes(self) -> None:
        with self.client.websocket_connect(f"/ws?token={VALID_TOKEN}") as websocket:
            ack = websocket.receive_json()
            self.assertEqual(ack["type"], "ack")
            websocket.send_json({"type": "text", "text": "ping"})
            response = websocket.receive_json()
            self.assertEqual(response["type"], "bot_text")
            self.assertEqual(response["text"], "echo: ping")

    def test_ws_rate_limit_enforced(self) -> None:
        with self.client.websocket_connect(f"/ws?token={VALID_TOKEN}") as websocket:
            websocket.receive_json()

        with self.client.websocket_connect(f"/ws?token={VALID_TOKEN}") as websocket:
            websocket.receive_json()

        with self.assertRaises(Exception):
            with self.client.websocket_connect(f"/ws?token={VALID_TOKEN}"):
                pass


if __name__ == "__main__":
    unittest.main()
