# Lyftr AI – Backend Assignment

## Project Overview

This project is a solution to the *Lyftr AI Backend Assignment*.  
The objective of the assignment is to design and implement a *secure, production-ready backend service* that ingests webhook events, persists data, exposes query and statistics APIs, and provides proper health checks and observability.

The service is implemented using *FastAPI* and follows real-world backend engineering practices including security, idempotency, validation, structured logging, and Prometheus-compatible metrics.

---

## What This Service Does

- Securely receives inbound webhook messages
- Validates and stores messages in a database
- Prevents duplicate message ingestion
- Exposes APIs to query messages and compute statistics
- Provides liveness and readiness health checks
- Exposes operational metrics for monitoring

---

## Tech Stack

- *Language:* Python 3
- *Framework:* FastAPI
- *Database:* SQLite (async)
- *Configuration:* Environment variables + .env
- *Observability:* Prometheus metrics, structured JSON logs
- *Security:* HMAC-SHA256 webhook signature verification

---

## Implemented Features

### Webhook Ingestion (POST /webhook)

- Accepts webhook events via HTTP POST
- Validates request payload:
  - Required fields
  - ISO-8601 UTC timestamps (Z suffix)
  - E.164 formatted phone numbers
- Verifies authenticity using *HMAC-SHA256*
- Ensures *idempotency* using message_id
- Stores valid messages in the database
- Handles webhook outcomes:
  - created
  - duplicate
  - invalid_signature
  - validation_error

*Important:*  
The webhook endpoint intentionally rejects browser access (GET /webhook) with *405 Method Not Allowed*.  
This is correct and expected behavior for a secure webhook endpoint.

---

### Health Checks

#### GET /health/live
- Returns 200 OK
- Confirms the service process is running

#### GET /health/ready
- Verifies:
  - Database availability
  - Presence of WEBHOOK_SECRET
- Returns 503 Service Unavailable if the service is not ready

---

### Messages API (GET /messages)

- Paginated retrieval of stored messages
- Supports filtering by:
  - Sender (from)
  - Timestamp (since)
  - Text search (q)
- Returns data along with total count and pagination metadata

---

### Statistics API (GET /stats)

- Computes aggregated statistics from stored messages
- Operates directly on persisted data

---

### Metrics (GET /metrics)

- Prometheus-compatible metrics endpoint
- Tracks:
  - Total HTTP requests (by path and status)
  - Request latency histogram
  - Webhook-specific result counters

---

### Logging & Observability

- Structured JSON logging
- Includes:
  - Timestamp
  - Request ID
  - HTTP method
  - Path
  - Status code
  - Latency
  - Webhook result (when applicable)

---

# Webhook Service Documentation

## Project Structure

app/
├── main.py           # FastAPI app, routes, middleware
├── config.py         # Environment configuration
├── storage.py        # Database connection and queries
├── metrics.py        # Prometheus metrics
├── logging_utils.py  # Structured logging helpers


## How to Run the Project

### 1. (Optional) Create a virtual environment
bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate


### 2. Install dependencies
bash
pip install -r requirements.txt


### 3. Start the server
bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000


## Sending a Valid Webhook Request

### Webhook Payload Example
json
{
  "message_id": "msg_123",
  "from": "+919999999999",
  "to": "+918888888888",
  "ts": "2026-01-15T09:28:35Z",
  "text": "Hello from webhook"
}


### Generating the Signature

The webhook signature is computed as:

HMAC_SHA256(WEBHOOK_SECRET, raw_request_body)


### Python Example
python
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


### Sending the Request
bash
curl -X POST http://127.0.0.1:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: <generated_signature>" \
  -d '<raw_json_payload>'


## Expected API Behavior

| Scenario | HTTP Status | Response |
|----------|-------------|----------|
| Valid webhook | 200 | { "status": "ok" } |
| Duplicate webhook | 200 | { "status": "ok" } |
| Invalid signature | 401 | { "detail": "invalid signature" } |
| Validation error | 422 | Validation details |
| GET on webhook | 405 | Method Not Allowed |