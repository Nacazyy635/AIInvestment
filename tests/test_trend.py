"""日足トレンド判定のユニットテスト（純粋関数・ネット不要）。

    python -m unittest discover -s tests -t .
"""
import unittest

import pandas as pd

from daytrader.models import Side
from daytrader.trend import trend_side


class TestTrendSide(unittest.TestCase):
    def _daily(self, closes):
        idx = pd.date_range("2026-04-01", periods=len(closes), freq="D", tz="Asia/Tokyo")
        return pd.DataFrame({"close": closes}, index=idx)

    def test_strong_uptrend_is_long(self):
        d = self._daily(list(range(100, 140)))  # 40日上昇
        sd = d.index[-1].date()                 # 最終日をsession→前日まで判定
        self.assertEqual(trend_side(d, sd, 25), Side.LONG)

    def test_weak_downtrend_is_short(self):
        d = self._daily(list(range(140, 100, -1)))  # 40日下降
        sd = d.index[-1].date()
        self.assertEqual(trend_side(d, sd, 25), Side.SHORT)

    def test_insufficient_history_is_none(self):
        d = self._daily(list(range(100, 110)))  # 10日 < 25
        sd = d.index[-1].date()
        self.assertIsNone(trend_side(d, sd, 25))

    def test_uses_only_prior_days(self):
        # 当日に巨大な値を入れても、前日までで判定するので影響しない
        closes = list(range(100, 140)) + [99999]
        d = self._daily(closes)
        sd = d.index[-1].date()  # 巨大値の日
        self.assertEqual(trend_side(d, sd, 25), Side.LONG)


if __name__ == "__main__":
    unittest.main()
