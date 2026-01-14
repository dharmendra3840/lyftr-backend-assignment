import hmac, hashlib, json
import pytest
from httpx import AsyncClient
from app.main import create_app
from app.config import Settings

def sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

async def post(ac, secret, payload):
    body = json.dumps(payload, separators=(",", ":")).encode()
    return await ac.post("/webhook", content=body, headers={"Content-Type":"application/json", "X-Signature":sign(secret, body)})

@pytest.mark.asyncio
async def test_stats(tmp_path):
    db = tmp_path / "app.db"
    secret = "testsecret"
    settings = Settings(DATABASE_URL=f"sqlite:////{db}", WEBHOOK_SECRET=secret, LOG_LEVEL="INFO")
    app = create_app(settings)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        await post(ac, secret, {"message_id":"m1","from":"+111","to":"+999","ts":"2025-01-10T09:00:00Z","text":"A"})
        await post(ac, secret, {"message_id":"m2","from":"+111","to":"+999","ts":"2025-01-11T09:00:00Z","text":"B"})
        await post(ac, secret, {"message_id":"m3","from":"+222","to":"+999","ts":"2025-01-15T10:00:00Z","text":"C"})

        r = await ac.get("/stats")
        j = r.json()
        assert j["total_messages"] == 3
        assert j["senders_count"] == 2
        assert j["first_message_ts"] == "2025-01-10T09:00:00Z"
        assert j["last_message_ts"] == "2025-01-15T10:00:00Z"