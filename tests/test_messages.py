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
async def test_messages_pagination_and_filters(tmp_path):
    db = tmp_path / "app.db"
    secret = "testsecret"
    settings = Settings(DATABASE_URL=f"sqlite:////{db}", WEBHOOK_SECRET=secret, LOG_LEVEL="INFO")
    app = create_app(settings)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        await post(ac, secret, {"message_id":"m1","from":"+100","to":"+200","ts":"2025-01-15T09:00:00Z","text":"Earlier"})
        await post(ac, secret, {"message_id":"m2","from":"+100","to":"+200","ts":"2025-01-15T10:00:00Z","text":"Hello"})
        await post(ac, secret, {"message_id":"m3","from":"+300","to":"+200","ts":"2025-01-15T11:00:00Z","text":"Other"})

        r = await ac.get("/messages?limit=2&offset=0")
        j = r.json()
        assert j["limit"] == 2
        assert j["offset"] == 0
        assert j["total"] == 3
        assert len(j["data"]) == 2

        r = await ac.get("/messages?from=%2B100")
        assert r.json()["total"] == 2

        r = await ac.get("/messages?since=2025-01-15T10:00:00Z")
        assert r.json()["total"] == 2

        r = await ac.get("/messages?q=hello")
        assert r.json()["total"] == 1