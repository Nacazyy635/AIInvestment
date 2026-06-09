"""エグジット判定のユニットテスト（純粋関数・ネット不要）。買い・売り両対応。

    python -m unittest discover -s tests -t .
"""
import unittest
from datetime import datetime, timedelta, timezone

from daytrader.exits import check_exit
from daytrader.models import ExitReason, Position, Side

JST = timezone(timedelta(hours=9))
FORCED = datetime(2026, 6, 9, 15, 25, tzinfo=JST)


def _long() -> Position:
    return Position(
        symbol="X", name="X", side=Side.LONG, qty=100,
        entry_ts=datetime(2026, 6, 9, 10, 0, tzinfo=JST),
        entry_price=1000.0, stop_price=995.0, take_price=1008.0,
        strategy_id="s", reason_open="entry",
    )


def _short() -> Position:
    # 売り: 損切りは上(1005)、利確は下(992)
    return Position(
        symbol="X", name="X", side=Side.SHORT, qty=100,
        entry_ts=datetime(2026, 6, 9, 10, 0, tzinfo=JST),
        entry_price=1000.0, stop_price=1005.0, take_price=992.0,
        strategy_id="s", reason_open="entry",
    )


def _ts(minute: int) -> datetime:
    return datetime(2026, 6, 9, 10, minute, tzinfo=JST)


class TestCheckExitLong(unittest.TestCase):
    def test_stop(self):
        res = check_exit(_long(), bar_high=1002, bar_low=994, bar_close=996,
                         bar_ts=_ts(5), time_exit_minutes=30, forced_close_ts=FORCED)
        self.assertEqual(res, (ExitReason.STOP_LOSS, 995.0))

    def test_take(self):
        res = check_exit(_long(), bar_high=1009, bar_low=1001, bar_close=1007,
                         bar_ts=_ts(5), time_exit_minutes=30, forced_close_ts=FORCED)
        self.assertEqual(res, (ExitReason.TAKE_PROFIT, 1008.0))

    def test_time(self):
        res = check_exit(_long(), bar_high=1002, bar_low=999, bar_close=1001,
                         bar_ts=_ts(30), time_exit_minutes=30, forced_close_ts=FORCED)
        self.assertEqual(res, (ExitReason.TIME_EXIT, 1001.0))

    def test_none(self):
        res = check_exit(_long(), bar_high=1003, bar_low=999, bar_close=1001,
                         bar_ts=_ts(10), time_exit_minutes=30, forced_close_ts=FORCED)
        self.assertIsNone(res)


class TestCheckExitShort(unittest.TestCase):
    def test_stop_on_high(self):
        # 売りの損切りは高値が逆指値(1005)以上
        res = check_exit(_short(), bar_high=1006, bar_low=1000, bar_close=1004,
                         bar_ts=_ts(5), time_exit_minutes=30, forced_close_ts=FORCED)
        self.assertEqual(res, (ExitReason.STOP_LOSS, 1005.0))

    def test_take_on_low(self):
        # 売りの利確は安値が利確値(992)以下
        res = check_exit(_short(), bar_high=1001, bar_low=991, bar_close=993,
                         bar_ts=_ts(5), time_exit_minutes=30, forced_close_ts=FORCED)
        self.assertEqual(res, (ExitReason.TAKE_PROFIT, 992.0))

    def test_forced(self):
        res = check_exit(_short(), bar_high=1001, bar_low=999, bar_close=1000,
                         bar_ts=FORCED, time_exit_minutes=30, forced_close_ts=FORCED)
        self.assertEqual(res, (ExitReason.FORCED_CLOSE, 1000.0))


if __name__ == "__main__":
    unittest.main()
