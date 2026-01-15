```md
## Project Structure

```
app/
├── main.py # FastAPI app, routes, middleware
├── config.py # Environment configuration
├── storage.py # Database connection and queries
├── metrics.py # Prometheus metrics
├── logging_utils.py # Structured logging helpers
```

## How to Run the Project

1. (Optional) Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Start the server

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Sending a Valid Webhook Request

### Webhook Payload Example

```json
{
  "message_id": "msg_123",
  "from": "+919999999999",
  "to": "+918888888888",
  "ts": "2026-01-15T09:28:35Z",
  "text": "Hello from webhook"
}
```

### Generating the Signature

The webhook signature is computed as:

```
HMAC_SHA256(WEBHOOK_SECRET, raw_request_body)
```

#### Python Example

```python
import hmac
import hashlib
import json

secret = b"supersecretkey"

payload = {
    "message_id": "msg_123",
    "from": "+919999999999",
    "to": "+918888888888",
    "ts": "2026-01-15T09:28:35Z",
    "text": "Hello from webhook"
}

raw_body = json.dumps(payload).encode("utf-8")
signature = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
print(signature)
```

### Sending the Request

```bash
curl -X POST http://127.0.0.1:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: <generated_signature>" \
  -d '<raw_json_payload>'
```

## Expected API Behavior

| Scenario          | HTTP Status | Response                       |
|------------------|------------:|--------------------------------|
| Valid webhook     | 200         | `{ "status": "ok" }`           |
| Duplicate webhook | 200         | `{ "status": "ok" }`           |
| Invalid signature | 401         | `{ "detail": "invalid signature" }` |
| Validation error  | 422         | Validation details             |
| GET on webhook    | 405         | Method Not Allowed             |
```