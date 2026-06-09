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

    def save(self, mode: str, trades: List[Trade]) -> None:
        """トレードを保存する。

        各トレードの entry_ts から session_date を導出し、
        同一 (session_date, mode) の既存行を入れ替える
        （バックテストを再実行しても重複しないように）。
        """
        if not trades:
            return
        dates = sorted({t.entry_ts.date().isoformat() for t in trades})
        cur = self.conn.cursor()
        for d in dates:
            cur.execute("DELETE FROM trades WHERE mode = ? AND session_date = ?", (mode, d))
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
                    t.symbol, t.name, t.strategy_id, mode, t.entry_ts.date().isoformat(), t.qty,
                    t.entry_ts.isoformat(), t.entry_price, t.exit_ts.isoformat(), t.exit_price,
                    t.pnl, t.pnl_pct, t.reason_open, t.reason_close,
                )
                for t in trades
            ],
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
