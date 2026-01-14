SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS messages (
  message_id TEXT PRIMARY KEY,
  from_msisdn TEXT NOT NULL,
  to_msisdn TEXT NOT NULL,
  ts TEXT NOT NULL,
  text TEXT,
  created_at TEXT NOT NULL
);
"""