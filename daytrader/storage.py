"""SQLite 永続化（Step2）。

トレード（完結した1往復）を保存する。SQLiteはサーバ不要のローカルファイルで、
エンジンと同じPC（運用時はWindows）に置く（仕様§6.2）。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List

from .models import Trade

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol       TEXT NOT NULL,
    name         TEXT,
    strategy_id  TEXT,
    mode         TEXT,
    session_date TEXT,
    qty          INTEGER,
    entry_ts     TEXT,
    entry_price  REAL,
    exit_ts      TEXT,
    exit_price   REAL,
    pnl          REAL,
    pnl_pct      REAL,
    reason_open  TEXT,
    reason_close TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);
"""


class Storage:
    """trades テーブルへの読み書き。"""

    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def replace_day(self, session_date: str, mode: str, trades: List[Trade]) -> None:
        """同一(日付, モード)の既存行を入れ替える（再実行で重複しないように）。"""
        cur = self.conn.cursor()
        cur.execute(
            "DELETE FROM trades WHERE mode = ? AND session_date = ?",
            (mode, session_date),
        )
        cur.executemany(
            """
            INSERT INTO trades
                (symbol, name, strategy_id, mode, session_date, qty,
                 entry_ts, entry_price, exit_ts, exit_price, pnl, pnl_pct,
                 reason_open, reason_close)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    t.symbol, t.name, t.strategy_id, mode, session_date, t.qty,
                    t.entry_ts.isoformat(), t.entry_price, t.exit_ts.isoformat(), t.exit_price,
                    t.pnl, t.pnl_pct, t.reason_open, t.reason_close,
                )
                for t in trades
            ],
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
