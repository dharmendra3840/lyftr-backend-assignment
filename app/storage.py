from __future__ import annotations

import aiosqlite
from typing import Any, Optional

from .models import SCHEMA_SQL


async def connect(db_path: str) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    # better concurrency for SQLite
    await conn.execute("PRAGMA journal_mode=WAL;")
    await conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


async def init_db(conn: aiosqlite.Connection) -> None:
    await conn.executescript(SCHEMA_SQL)
    await conn.commit()


async def db_is_ready(conn: aiosqlite.Connection) -> bool:
    try:
        await conn.execute("SELECT 1;")
        cur = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='messages';"
        )
        row = await cur.fetchone()
        return row is not None
    except Exception:
        return False


async def insert_message(
    conn: aiosqlite.Connection,
    *,
    message_id: str,
    from_msisdn: str,
    to_msisdn: str,
    ts: str,
    text: Optional[str],
    created_at: str,
) -> bool:
    """
    Returns True if created, False if duplicate (idempotent).
    """
    cur = await conn.execute(
        """
        INSERT OR IGNORE INTO messages(message_id, from_msisdn, to_msisdn, ts, text, created_at)
        VALUES(?,?,?,?,?,?)
        """,
        (message_id, from_msisdn, to_msisdn, ts, text, created_at),
    )
    await conn.commit()
    return cur.rowcount == 1


def _normalize_from_query(v: str) -> str:
    # curl often sends ?from=+123..., and frameworks may decode '+' as space.
    # Normalize:
    s = v.strip()
    if s and not s.startswith("+") and s.isdigit():
        return "+" + s
    return s


async def list_messages(
    conn: aiosqlite.Connection,
    *,
    limit: int,
    offset: int,
    from_filter: Optional[str],
    since: Optional[str],
    q: Optional[str],
) -> tuple[list[dict[str, Any]], int]:
    where = []
    args: list[Any] = []

    if from_filter:
        from_filter = _normalize_from_query(from_filter)
        where.append("from_msisdn = ?")
        args.append(from_filter)

    if since:
        where.append("ts >= ?")
        args.append(since)

    if q:
        where.append("text IS NOT NULL AND lower(text) LIKE '%' || lower(?) || '%'")
        args.append(q)

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    # total
    cur = await conn.execute(f"SELECT COUNT(*) AS c FROM messages{where_sql}", args)
    total = int((await cur.fetchone())["c"])

    # page
    cur = await conn.execute(
        f"""
        SELECT message_id, from_msisdn, to_msisdn, ts, text
        FROM messages
        {where_sql}
        ORDER BY ts ASC, message_id ASC
        LIMIT ? OFFSET ?
        """,
        args + [limit, offset],
    )
    rows = await cur.fetchall()

    data = []
    for r in rows:
        data.append(
            {
                "message_id": r["message_id"],
                "from": r["from_msisdn"],
                "to": r["to_msisdn"],
                "ts": r["ts"],
                "text": r["text"],
            }
        )
    return data, total


async def compute_stats(conn: aiosqlite.Connection) -> dict[str, Any]:
    cur = await conn.execute("SELECT COUNT(*) AS c FROM messages;")
    total_messages = int((await cur.fetchone())["c"])

    cur = await conn.execute("SELECT COUNT(DISTINCT from_msisdn) AS c FROM messages;")
    senders_count = int((await cur.fetchone())["c"])

    cur = await conn.execute(
        """
        SELECT from_msisdn AS sender, COUNT(*) AS c
        FROM messages
        GROUP BY from_msisdn
        ORDER BY c DESC, sender ASC
        LIMIT 10;
        """
    )
    top = await cur.fetchall()
    messages_per_sender = [{"from": r["sender"], "count": int(r["c"])} for r in top]

    cur = await conn.execute("SELECT MIN(ts) AS min_ts, MAX(ts) AS max_ts FROM messages;")
    row = await cur.fetchone()

    first_ts = row["min_ts"]
    last_ts = row["max_ts"]

    return {
        "total_messages": total_messages,
        "senders_count": senders_count,
        "messages_per_sender": messages_per_sender,
        "first_message_ts": first_ts,
        "last_message_ts": last_ts,
    }