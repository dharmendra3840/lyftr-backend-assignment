from __future__ import annotations

import hmac
import hashlib
import json
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, field_validator

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from .config import Settings
from .logging_utils import build_logger, log_json, utc_now_iso
from .metrics import HTTP_REQUESTS_TOTAL, REQUEST_LATENCY_MS, WEBHOOK_REQUESTS_TOTAL
from .storage import connect, init_db, db_is_ready, insert_message, list_messages, compute_stats


# ---------- Pydantic models ----------

E164_RE = r"^\+\d+$"


def _parse_ts_z(ts: str) -> str:
    # Must end with Z and be valid UTC timestamp. Store as canonical "...Z" without micros.
    if not isinstance(ts, str) or not ts.endswith("Z"):
        raise ValueError("ts must be ISO-8601 UTC with Z suffix (e.g. 2025-01-15T10:00:00Z)")
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception as e:
        raise ValueError("ts must be a valid ISO-8601 timestamp") from e

    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")


class WebhookIn(BaseModel):
    message_id: str = Field(min_length=1)
    from_msisdn: str = Field(alias="from", pattern=E164_RE)
    to_msisdn: str = Field(alias="to", pattern=E164_RE)
    ts: str
    text: Optional[str] = Field(default=None, max_length=4096)

    @field_validator("ts")
    @classmethod
    def validate_ts(cls, v: str) -> str:
        return _parse_ts_z(v)


class StatusOut(BaseModel):
    status: str = "ok"


# ---------- App factory ----------

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    logger = build_logger("api", settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Hard fail if secret missing (matches requirement)
        if not settings.webhook_secret:
            raise RuntimeError("WEBHOOK_SECRET must be set and non-empty")

        conn = await connect(settings.sqlite_path)
        await init_db(conn)

        app.state.settings = settings
        app.state.db = conn
        app.state.logger = logger
        yield

        await conn.close()

    app = FastAPI(lifespan=lifespan)

    # ---------- Middleware: signature verification for /webhook ----------
    @app.middleware("http")
    async def webhook_signature_middleware(request: Request, call_next):
        if request.method == "POST" and request.url.path == "/webhook":
            secret = request.app.state.settings.webhook_secret.encode("utf-8")
            raw = await request.body()

            sig = request.headers.get("X-Signature")
            expected = hmac.new(secret, raw, hashlib.sha256).hexdigest()

            if not sig or not hmac.compare_digest(sig.lower(), expected.lower()):
                # Put info into request.state for logging/metrics
                request.state.webhook_result = "invalid_signature"
                request.state.webhook_dup = False
                try:
                    body_json = json.loads(raw.decode("utf-8"))
                    request.state.webhook_message_id = body_json.get("message_id")
                except Exception:
                    request.state.webhook_message_id = None

                return JSONResponse(status_code=401, content={"detail": "invalid signature"})

        return await call_next(request)

    # ---------- Middleware: request_id + logging + metrics ----------
    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()

        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # unhandled exception path
            status_code = 500
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000.0
            path = request.url.path

            # metrics
            HTTP_REQUESTS_TOTAL.labels(path=path, status=str(status_code)).inc()
            REQUEST_LATENCY_MS.observe(latency_ms)

            result = getattr(request.state, "webhook_result", None)
            if path == "/webhook" and result:
                WEBHOOK_REQUESTS_TOTAL.labels(result=result).inc()

            # log level
            if path == "/webhook" and result == "invalid_signature":
                level = 40  # ERROR
            elif status_code >= 500:
                level = 40
            elif status_code >= 400:
                level = 30  # WARNING
            else:
                level = 20  # INFO

            log_payload = {
                "ts": utc_now_iso(),
                "level": logging_level_name(level),
                "request_id": request_id,
                "method": request.method,
                "path": path,
                "status": status_code,
                "latency_ms": round(latency_ms, 2),
            }

            if path == "/webhook":
                log_payload.update(
                    {
                        "message_id": getattr(request.state, "webhook_message_id", None),
                        "dup": getattr(request.state, "webhook_dup", None),
                        "result": getattr(request.state, "webhook_result", None),
                    }
                )

            log_json(request.app.state.logger, level, log_payload)

        response.headers["X-Request-ID"] = request_id
        return response

    def logging_level_name(level: int) -> str:
        if level >= 40:
            return "ERROR"
        if level >= 30:
            return "WARNING"
        if level >= 20:
            return "INFO"
        return "DEBUG"

    # ---------- Exception handler: mark webhook validation errors for metrics/logs ----------
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        if request.url.path == "/webhook":
            request.state.webhook_result = "validation_error"
            request.state.webhook_dup = False
            # try to extract message_id if present
            try:
                if isinstance(exc.body, dict):
                    request.state.webhook_message_id = exc.body.get("message_id")
            except Exception:
                pass
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    # ---------- Routes ----------

    @app.get("/health/live")
    async def health_live():
        return {"status": "live"}

    @app.get("/health/ready")
    async def health_ready(request: Request):
        settings: Settings = request.app.state.settings
        conn = request.app.state.db

        if not settings.webhook_secret:
            return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "missing WEBHOOK_SECRET"})

        ok = await db_is_ready(conn)
        if not ok:
            return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "db not ready"})

        return {"status": "ready"}

    @app.post("/webhook", response_model=StatusOut)
    async def webhook(request: Request, payload: WebhookIn):
        # signature already verified in middleware if we got here
        created_at = utc_now_iso()
        conn = request.app.state.db

        created = await insert_message(
            conn,
            message_id=payload.message_id,
            from_msisdn=payload.from_msisdn,
            to_msisdn=payload.to_msisdn,
            ts=payload.ts,
            text=payload.text,
            created_at=created_at,
        )

        request.state.webhook_message_id = payload.message_id
        request.state.webhook_dup = (not created)
        request.state.webhook_result = "created" if created else "duplicate"

        return {"status": "ok"}

    @app.get("/messages")
    async def get_messages(
        request: Request,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        from_: Optional[str] = Query(None, alias="from"),
        since: Optional[str] = Query(None),
        q: Optional[str] = Query(None),
    ):
        if since is not None:
            # Validate since format the same way as ts
            since = _parse_ts_z(since)

        data, total = await list_messages(
            request.app.state.db,
            limit=limit,
            offset=offset,
            from_filter=from_,
            since=since,
            q=q,
        )
        return {"data": data, "total": total, "limit": limit, "offset": offset}

    @app.get("/stats")
    async def stats(request: Request):
        return await compute_stats(request.app.state.db)

    @app.get("/metrics")
    async def metrics():
        output = generate_latest()
        return PlainTextResponse(content=output.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()