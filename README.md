```md
# Lyftr AI – Backend Assignment

## Project Overview

This project is a solution to the **Lyftr AI Backend Assignment**.  
It implements a **secure, production-ready backend service** that ingests webhook events, persists data, exposes query/statistics APIs, and provides health checks + observability.

Built with **FastAPI**, following real-world backend practices: security, idempotency, validation, structured logging, and Prometheus-compatible metrics.

---

## What This Service Does

- Securely receives inbound webhook messages
- Validates and stores messages in a database
- Prevents duplicate message ingestion (idempotency via `message_id`)
- Exposes APIs to query messages and compute statistics
- Provides liveness and readiness health checks
- Exposes operational metrics for monitoring

---

## Tech Stack

- **Language:** Python 3
- **Framework:** FastAPI
- **Database:** SQLite (async)
- **Configuration:** Environment variables + `.env`
- **Observability:** Prometheus metrics, structured JSON logs
- **Security:** HMAC-SHA256 webhook signature verification

---

## Implemented Features

### Webhook Ingestion — `POST /webhook`

- Accepts webhook events via HTTP POST
- Validates request payload:
  - Required fields
  - ISO-8601 UTC timestamps (`Z` suffix)
  - E.164 formatted phone numbers
- Verifies authenticity using **HMAC-SHA256**
- Ensures **idempotency** using `message_id`
- Stores valid messages in the database

> Note: `GET /webhook` is intentionally **not allowed** and returns **405 Method Not Allowed**.  
> This is expected behavior for a secure webhook endpoint.

### Health Checks

- **GET `/health/live`**  
  Returns `200 OK` if the process is running.

- **GET `/health/ready`**  
  Verifies:
  - Database availability
  - Presence of `WEBHOOK_SECRET`  
  Returns `503 Service Unavailable` if not ready.

### Messages API — `GET /messages`

- Paginated retrieval of stored messages
- Supports filtering by:
  - sender (`from`)
  - timestamp (`since`)
  - text search (`q`)
- Returns items + pagination metadata and total count

### Statistics API — `GET /stats`

- Computes aggregated statistics based on stored messages

### Metrics — `GET /metrics`

Prometheus-compatible metrics endpoint, including:
- Total HTTP requests (by path and status)
- Request latency histogram
- Webhook result counters (created/duplicate/invalid_signature/validation_error)

### Logging & Observability

- Structured JSON logging including:
  - timestamp
  - request ID
  - method, path
  - status code
  - latency
  - webhook result (when applicable)

---

## Project Structure

```text
app/
├── main.py           # FastAPI app, routes, middleware
├── config.py         # Environment configuration
├── storage.py        # Database connection and queries
├── metrics.py        # Prometheus metrics
├── logging_utils.py  # Structured logging helpers
```

---

## How to Run

### 1) (Optional) Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Configure environment

Set `WEBHOOK_SECRET` (required for readiness and signature verification).

Example:

```bash
export WEBHOOK_SECRET="supersecretkey"
```

Or create a `.env` file (if supported by your setup):

```env
WEBHOOK_SECRET=supersecretkey
```

### 4) Start the server

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

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

### Signature Generation

The webhook signature is computed as:

```text
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

### Send the Request (curl)

> Replace `<generated_signature>` and `<raw_json_payload>`.

```bash
curl -X POST "http://127.0.0.1:8000/webhook" \
  -H "Content-Type: application/json" \
  -H "X-Signature: <generated_signature>" \
  -d '<raw_json_payload>'
```

---

## Expected API Behavior

| Scenario           | HTTP Status | Response                             |
|-------------------|------------:|--------------------------------------|
| Valid webhook      | 200         | `{ "status": "ok" }`                 |
| Duplicate webhook  | 200         | `{ "status": "ok" }`                 |
| Invalid signature  | 401         | `{ "detail": "invalid signature" }`  |
| Validation error   | 422         | Validation details                   |
| `GET /webhook`     | 405         | Method Not Allowed                   |

---

## Useful Endpoints

```text
POST /webhook
GET  /health/live
GET  /health/ready
GET  /messages
GET  /stats
GET  /metrics
```
```