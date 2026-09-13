"""Starea aplicaţiei. Puţină, fiindcă lucrul greu stă în fişiere pe volum."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

DATA = os.environ.get("DATA_DIR", "data")
CALE = os.path.join(DATA, "faceslice.db")


def acum() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conn() -> sqlite3.Connection:
    os.makedirs(DATA, exist_ok=True)
    c = sqlite3.connect(CALE, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


DB = conn()

DB.executescript("""
CREATE TABLE IF NOT EXISTS devices (
  id         TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  label      TEXT,
  created_at TEXT NOT NULL,
  last_seen  TEXT,
  revoked    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS invites (
  id         TEXT PRIMARY KEY,
  code_hash  TEXT NOT NULL UNIQUE,
  code       TEXT,
  label      TEXT,
  url        TEXT,
  created_at TEXT NOT NULL,
  expires_at TEXT,
  used_at    TEXT,
  revoked    INTEGER NOT NULL DEFAULT 0,
  device_id  TEXT
);
-- O lucrare = o fotografie reconstruită. Harta de adâncime stă pe disc, nu
-- aici: e un tablou de câteva megaocteţi şi n-are ce căuta într-un rând.
CREATE TABLE IF NOT EXISTS jobs (
  id         TEXT PRIMARY KEY,
  device_id  TEXT NOT NULL,
  created_at TEXT NOT NULL,
  nume       TEXT,
  rezumat    TEXT,
  reglaje    TEXT
);
CREATE INDEX IF NOT EXISTS jobs_device ON jobs(device_id, created_at DESC);
""")
DB.commit()


def dosar_job(job_id: str) -> str:
    d = os.path.join(DATA, "jobs", job_id)
    os.makedirs(d, exist_ok=True)
    return d
