import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_NAME = 'kiln.sqlite3'

SCHEMA = """
CREATE TABLE IF NOT EXISTS kiln_batches (
  batch       TEXT PRIMARY KEY,
  stock_g     INTEGER NOT NULL,
  moisture_bp INTEGER NOT NULL,
  remainder_g INTEGER NOT NULL,
  created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS kiln_loads (
  load            TEXT PRIMARY KEY,
  batch           TEXT NOT NULL REFERENCES kiln_batches(batch),
  seq             INTEGER NOT NULL,
  charged_g       INTEGER NOT NULL,
  moisture_in_bp  INTEGER NOT NULL,
  status          TEXT NOT NULL,              -- DRYING | WEIGHED | HOLD
  weighed_g       INTEGER,
  moisture_out_bp INTEGER,
  drawn_g         INTEGER NOT NULL DEFAULT 0,
  ledger_json     TEXT,
  created_at      TEXT NOT NULL,
  registered_at   TEXT,
  UNIQUE (batch, seq)
);
CREATE INDEX IF NOT EXISTS idx_kiln_loads_batch ON kiln_loads(batch, seq);
CREATE TABLE IF NOT EXISTS kiln_requisitions (
  req        TEXT PRIMARY KEY,
  batch      TEXT NOT NULL,
  amount_g   INTEGER NOT NULL,
  load_ref   TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS kiln_req_lines (
  req    TEXT NOT NULL REFERENCES kiln_requisitions(req),
  batch  TEXT NOT NULL,
  source TEXT NOT NULL,                       -- 炉次号或 REMAINDER
  load   TEXT,
  grams  INTEGER NOT NULL,
  PRIMARY KEY (req, source)
);
"""


def db_path(root):
    return Path(root) / DB_NAME


def exists(root):
    return db_path(root).exists()


def connect(root):
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path / DB_NAME, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=15000')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def transaction(root):
    """所有领料/登记都在 BEGIN IMMEDIATE 下进行：写事务全局串行，
    “读取余量 -> 判定 -> 扣减”期间不会被另一张单插入，因此两单同提也不会领超同一炉。"""
    conn = connect(root)
    conn.execute('BEGIN IMMEDIATE')
    try:
        yield conn
        conn.execute('COMMIT')
    except BaseException:
        conn.execute('ROLLBACK')
        raise
    finally:
        conn.close()


@contextmanager
def reader(root):
    """只读事务：批次头与炉次/领料行取自同一快照，避免并发提交拼出半新半旧的试算表。"""
    conn = connect(root)
    conn.execute('BEGIN')
    try:
        yield conn
        conn.execute('COMMIT')
    except BaseException:
        conn.execute('ROLLBACK')
        raise
    finally:
        conn.close()
