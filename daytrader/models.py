"""ドメインのデータ構造。

「何を扱うか」を型で固定しておくと、後段（通知・DB保存・AI補助）が
このオブジェクトを受け取るだけで済み、各モジュールの結合が緩くなる。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SignalType(str, Enum):
    """シグナルの種別。MVPは買いのみ。将来 SELL / SHORT を追加。"""
    BUY = "BUY"


@dataclass(frozen=True)
class IndicatorSnapshot:
    """あるバー時点の指標スナップショット（通知・記録用）。"""
    price: float          # 終値
    vwap: float           # 当日VWAP
    ma: float             # 移動平均
    volume: float         # そのバーの出来高
    volume_avg: float     # 出来高移動平均
    recent_high: float    # 直近高値（現バーを含めない）

    @property
    def vwap_diff_pct(self) -> float:
        """VWAPからの乖離率（％）。"""
        if self.vwap == 0:
            return 0.0
        return (self.price - self.vwap) / self.vwap * 100.0

    @property
    def volume_ratio(self) -> float:
        """出来高が平均の何倍か。"""
        if self.volume_avg == 0:
            return 0.0
        return self.volume / self.volume_avg


@dataclass(frozen=True)
class Signal:
    """戦略が検出したエントリー候補。Step1では通知のみ（発注しない）。"""
    symbol: str
    name: str
    type: SignalType
    timestamp: datetime
    strategy_id: str
    indicators: IndicatorSnapshot
    reason: str

    @property
    def key(self) -> str:
        """重複通知を防ぐための一意キー（銘柄＋時刻）。"""
        return f"{self.symbol}:{self.timestamp.isoformat()}"
