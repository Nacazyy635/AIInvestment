"""戦略の時間帯フィルタのユニットテスト（純粋関数なのでネット不要）。

    python -m unittest discover -s tests -t .
"""
import unittest

import pandas as pd

from daytrader.strategy import _hhmm_to_min, allowed_entry_mask


class TestEntryTimeWindow(unittest.TestCase):
    def _mask(self, times):
        idx = pd.DatetimeIndex(
            [pd.Timestamp(f"2026-06-09 {t}", tz="Asia/Tokyo") for t in times]
        )
        return allowed_entry_mask(
            idx,
            open_min=_hhmm_to_min("09:00"),
            morning_close_min=_hhmm_to_min("11:30"),
            afternoon_open_min=_hhmm_to_min("12:30"),
            close_min=_hhmm_to_min("15:30"),
            skip_open=5,
            skip_close=30,
        ).tolist()

    def test_morning_open_skip(self):
        # 9:00-9:04 は除外、9:05 から許可
        self.assertEqual(self._mask(["09:02", "09:05", "10:00"]), [False, True, True])

    def test_afternoon_open_skip(self):
        # 後場寄り 12:30-12:34 は除外、12:35 から許可
        self.assertEqual(self._mask(["12:31", "12:35", "13:00"]), [False, True, True])

    def test_before_close_skip(self):
        # skip_close=30 → 15:30-30=15:00 まで許可、それ以降は除外
        self.assertEqual(self._mask(["14:59", "15:00", "15:10", "15:24"]), [True, True, False, False])

    def test_lunch_is_excluded(self):
        # 昼休み(11:30-12:30)は前場・後場どちらの枠にも入らない
        self.assertEqual(self._mask(["11:45", "12:00"]), [False, False])


class TestStrategyFactory(unittest.TestCase):
    def _make(self, name):
        from daytrader.config import MarketConfig, StrategyParams
        from daytrader.strategy import make_strategy
        return make_strategy(name, StrategyParams(), MarketConfig())

    def test_make_breakout(self):
        from daytrader.strategy import VwapBreakoutStrategy
        self.assertIsInstance(self._make("vwap_breakout"), VwapBreakoutStrategy)

    def test_make_reversion(self):
        from daytrader.strategy import VwapReversionStrategy
        self.assertIsInstance(self._make("vwap_reversion"), VwapReversionStrategy)

    def test_unknown_defaults_to_breakout(self):
        from daytrader.strategy import VwapBreakoutStrategy
        self.assertIsInstance(self._make("nope"), VwapBreakoutStrategy)


if __name__ == "__main__":
    unittest.main()
