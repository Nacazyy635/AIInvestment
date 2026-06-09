"""ポジションサイジング（円ベース・100株単位）。

固定株数だと値がさ株ほど損益が大きく出てしまい、銘柄間の比較が歪む。
そこで「1ポジあたりの代金」を一定に保つよう、目標金額に近い単元数を算出する。
"""
from __future__ import annotations


def position_size(price: float, target_yen: float, max_yen: float, unit: int = 100) -> int:
    """目標金額に最も近い株数（unit株刻み）を返す。

    - 最低 1単元（unit株）。
    - 1単元でも max_yen を超える高すぎる銘柄は 0（=スキップ）を返す。
    """
    if price <= 0:
        return 0
    if unit * price > max_yen:
        return 0
    units = max(1, int(target_yen / (price * unit) + 0.5))  # 四捨五入で最も近い単元数
    return units * unit
