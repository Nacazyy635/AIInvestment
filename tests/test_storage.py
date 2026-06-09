"""SQLite永続化のユニットテスト（一時DBを使用・ネット不要）。

    python -m unittest discover -s tests -t .
"""
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from daytrader.models import Trade
from daytrader.storage import Storage

JST = timezone(timedelta(hours=9))


def _trade(symbol: str, day: int, exit_price: float) -> Trade:
    return Trade(
        symbol=symbol, name=symbol, strategy_id="s", qty=100,
        entry_ts=datetime(2026, 6, day, 10, 0, tzinfo=JST), entry_price=1000.0,
        exit_ts=datetime(2026, 6, day, 10, 30, tzinfo=JST), exit_price=exit_price,
        reason_open="o", reason_close="TIME_EXIT",
    )


class TestStorage(unittest.TestCase):
    def test_save_and_replace_by_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = Storage(os.path.join(tmp, "t.db"))
            # 9日に2件・10日に1件
            s.save("PAPER", [_trade("A.T", 9, 1005.0), _trade("B.T", 9, 995.0), _trade("A.T", 10, 1010.0)])
            self.assertEqual(self._count(s), 3)

            # 9日を再保存 → 9日分だけ入れ替わる（10日は残る）
            s.save("PAPER", [_trade("A.T", 9, 1002.0)])
            self.assertEqual(self._count(s, "2026-06-09"), 1)
            self.assertEqual(self._count(s, "2026-06-10"), 1)
            self.assertEqual(self._count(s), 2)
            s.close()

    def test_pnl_stored(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = Storage(os.path.join(tmp, "t.db"))
            s.save("PAPER", [_trade("A.T", 9, 1005.0)])  # +5円×100株 = +500
            pnl = s.conn.execute("SELECT pnl FROM trades").fetchone()[0]
            self.assertAlmostEqual(pnl, 500.0)
            s.close()

    @staticmethod
    def _count(s: Storage, session_date: str = None) -> int:
        if session_date:
            return s.conn.execute(
                "SELECT count(*) FROM trades WHERE session_date=?", (session_date,)
            ).fetchone()[0]
        return s.conn.execute("SELECT count(*) FROM trades").fetchone()[0]


if __name__ == "__main__":
    unittest.main()
