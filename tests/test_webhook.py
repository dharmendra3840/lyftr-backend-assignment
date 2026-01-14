import hmac, hashlib, json
import pytest
from httpx import AsyncClient
from app.main import create_app
from app.config import Settings

def sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

@pytest.mark.asyncio
async def test_webhook_valid_and_duplicate(tmp_path):
    db = tmp_path / "app.db"
    settings = Settings(DATABASE_URL=f"sqlite:////{db}", WEBHOOK_SECRET="testsecret", LOG_LEVEL="INFO")
    app = create_app(settings)

    body = json.dumps({
        "message_id":"m1",
        "from":"+919876543210",
        "to":"+14155550100",
        "ts":"2025-01-15T10:00:00Z",
        "text":"Hello"
    }, separators=(",", ":")).encode()

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # invalid signature
        r = await ac.post("/webhook", content=body, headers={"Content-Type":"application/json", "X-Signature":"123"})
        assert r.status_code == 401

        # valid signature, created
        r = await ac.post("/webhook", content=body, headers={"Content-Type":"application/json", "X-Signature":sign("testsecret", body)})
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        # duplicate, still 200
        r = await ac.post("/webhook", content=body, headers={"Content-Type":"application/json", "X-Signature":sign("testsecret", body)})
        assert r.status_code == 200