"""指標計算のユニットテスト（ネットワーク不要・stdlibのみ）。

    python -m unittest discover -s tests -t .
"""
import unittest

import pandas as pd

from daytrader.indicators import add_indicators, typical_price


class TestIndicators(unittest.TestCase):
    def _df(self) -> pd.DataFrame:
        idx = pd.date_range("2026-06-09 09:00", periods=3, freq="1min", tz="Asia/Tokyo")
        return pd.DataFrame(
            {
                "open": [100, 101, 102],
                "high": [101, 102, 103],
                "low": [99, 100, 101],
                "close": [100, 102, 102],
                "volume": [100, 200, 300],
            },
            index=idx,
        )

    def test_typical_price(self):
        tp = typical_price(self._df())
        self.assertAlmostEqual(tp.iloc[0], (101 + 99 + 100) / 3)

    def test_columns_added(self):
        d = add_indicators(self._df(), ma_period=2, volume_window=2, recent_high_window=2)
        for col in ["vwap", "ma", "volume_avg", "recent_high"]:
            self.assertIn(col, d.columns)

    def test_vwap_first_bar_equals_typical_price(self):
        # 1本目のVWAP = 代表値（出来高加重でも1本目は自分自身）
        d = add_indicators(self._df(), ma_period=2, volume_window=2, recent_high_window=2)
        self.assertAlmostEqual(d["vwap"].iloc[0], (101 + 99 + 100) / 3)

    def test_vwap_weighted_second_bar(self):
        # 2本目VWAP = Σ(tp*vol)/Σ(vol)
        tp0, tp1 = (101 + 99 + 100) / 3, (102 + 100 + 102) / 3
        expected = (tp0 * 100 + tp1 * 200) / (100 + 200)
        d = add_indicators(self._df(), ma_period=2, volume_window=2, recent_high_window=2)
        self.assertAlmostEqual(d["vwap"].iloc[1], expected)

    def test_recent_high_excludes_current_bar(self):
        # 2本目のrecent_highは1本目のhigh(=101)。現バーを含めない。
        d = add_indicators(self._df(), ma_period=2, volume_window=2, recent_high_window=2)
        self.assertEqual(d["recent_high"].iloc[1], 101)


if __name__ == "__main__":
    unittest.main()
