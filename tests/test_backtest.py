"""エグジット判定のユニットテスト（純粋関数・ネット不要）。

    python -m unittest discover -s tests -t .
"""
import unittest
from datetime import datetime, timedelta, timezone

from daytrader.exits import check_exit
from daytrader.models import ExitReason, Position

JST = timezone(timedelta(hours=9))


def _position() -> Position:
    return Position(
        symbol="X", name="X", qty=100,
        entry_ts=datetime(2026, 6, 9, 10, 0, tzinfo=JST),
        entry_price=1000.0, stop_price=995.0, take_price=1008.0,
        strategy_id="s", reason_open="entry",
    )


FORCED = datetime(2026, 6, 9, 15, 25, tzinfo=JST)


class TestCheckExit(unittest.TestCase):
    def test_stop_loss_when_low_touches(self):
        ts = datetime(2026, 6, 9, 10, 5, tzinfo=JST)
        res = check_exit(_position(), bar_high=1002, bar_low=994, bar_close=996,
                         bar_ts=ts, time_exit_minutes=30, forced_close_ts=FORCED)
        self.assertEqual(res, (ExitReason.STOP_LOSS, 995.0))

    def test_take_profit_when_high_touches(self):
        ts = datetime(2026, 6, 9, 10, 5, tzinfo=JST)
        res = check_exit(_position(), bar_high=1009, bar_low=1001, bar_close=1007,
                         bar_ts=ts, time_exit_minutes=30, forced_close_ts=FORCED)
        self.assertEqual(res, (ExitReason.TAKE_PROFIT, 1008.0))

    def test_stop_priority_when_both_touch(self):
        # 同一バーで損切り・利確の両方に触れたら損切り優先（保守的）
        ts = datetime(2026, 6, 9, 10, 5, tzinfo=JST)
        res = check_exit(_position(), bar_high=1009, bar_low=994, bar_close=1000,
                         bar_ts=ts, time_exit_minutes=30, forced_close_ts=FORCED)
        self.assertEqual(res[0], ExitReason.STOP_LOSS)

    def test_time_exit(self):
        ts = datetime(2026, 6, 9, 10, 30, tzinfo=JST)  # 入場から30分
        res = check_exit(_position(), bar_high=1002, bar_low=999, bar_close=1001,
                         bar_ts=ts, time_exit_minutes=30, forced_close_ts=FORCED)
        self.assertEqual(res, (ExitReason.TIME_EXIT, 1001.0))

    def test_forced_close(self):
        ts = datetime(2026, 6, 9, 15, 25, tzinfo=JST)
        res = check_exit(_position(), bar_high=1002, bar_low=999, bar_close=1001,
                         bar_ts=ts, time_exit_minutes=30, forced_close_ts=FORCED)
        self.assertEqual(res, (ExitReason.FORCED_CLOSE, 1001.0))

    def test_no_exit(self):
        ts = datetime(2026, 6, 9, 10, 10, tzinfo=JST)
        res = check_exit(_position(), bar_high=1003, bar_low=999, bar_close=1001,
                         bar_ts=ts, time_exit_minutes=30, forced_close_ts=FORCED)
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
