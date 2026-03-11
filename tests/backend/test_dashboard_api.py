from fastapi.testclient import TestClient
import os

os.environ["USE_AWS_MOCKS"] = "true"

from backend.app.main import app

client = TestClient(app)

def test_knowledge_stats_returns_shape():
    resp = client.get("/api/knowledge-stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_chunks" in data
    assert "total_documents" in data
    assert "last_ingested" in data
    assert isinstance(data["total_chunks"], int)
    assert "source" in data
    assert data["source"] == "mock"
