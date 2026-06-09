"""円ベース・ポジションサイジングのユニットテスト。

    python -m unittest discover -s tests -t .
"""
import unittest

from daytrader.sizing import position_size

TARGET = 350000
MAX = 550000


class TestPositionSize(unittest.TestCase):
    def test_low_priced_scales_up(self):
        # 日産 336円 → 35万に近い単元 = 10単元 = 1000株（約33.6万）
        self.assertEqual(position_size(336, TARGET, MAX), 1000)

    def test_mercari_one_unit(self):
        # メルカリ 3600円 → 100株（約36万）。1単元が最も近い
        self.assertEqual(position_size(3600, TARGET, MAX), 100)

    def test_mid_priced_rounds(self):
        # 2000円 → 350000/200000=1.75 → 四捨五入で2単元 = 200株
        self.assertEqual(position_size(2000, TARGET, MAX), 200)

    def test_min_one_unit(self):
        # 5000円 → 0.7単元でも最低1単元 = 100株（50万 ≤ max55万）
        self.assertEqual(position_size(5000, TARGET, MAX), 100)

    def test_skip_too_expensive(self):
        # 6000円 → 100株=60万 > max55万 → 0（スキップ）
        self.assertEqual(position_size(6000, TARGET, MAX), 0)


if __name__ == "__main__":
    unittest.main()
