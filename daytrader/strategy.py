"""売買戦略（シグナル判定）。

`Strategy` 抽象に対し、MVPの `VwapBreakoutStrategy`（VWAP順張り）を実装。
戦略を差し替え可能にしておくことで、将来オープニングレンジ・ブレイク等を
`strategy_id` で追加できる（仕様§5.2）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, time

import pandas as pd

from .config import StrategyParams
from .indicators import add_indicators
from .models import IndicatorSnapshot, Signal, SignalType


class Strategy(ABC):
    strategy_id: str

    @abstractmethod
    def evaluate(self, symbol: str, name: str, df: pd.DataFrame) -> list[Signal]:
        """分足DataFrameを受け取り、当日のエントリー候補を全て返す。"""
        raise NotImplementedError


class VwapBreakoutStrategy(Strategy):
    """VWAP順張り（買いのみ）。仕様§5.2。

    エントリー条件（すべて満たす）:
      1) 終値がVWAPを上抜け（前バーはVWAP以下、現バーはVWAP超）
      2) 出来高増加（現バー出来高 ≥ volume_factor × 出来高移動平均）
      3) 直近高値を更新（終値 > 直近 recent_high_window 本の高値）
      4) 寄り直後の板寄せ時間帯を除外（skip_minutes_after_open）

    Step1では検出して通知するのみ（発注しない）。
    """
    strategy_id = "vwap_breakout"

    def __init__(self, params: StrategyParams, market_open: time, skip_minutes: int):
        self.p = params
        self.market_open = market_open
        self.skip_minutes = skip_minutes

    def evaluate(self, symbol: str, name: str, df: pd.DataFrame) -> list[Signal]:
        if len(df) < 2:
            return []

        d = add_indicators(
            df,
            ma_period=self.p.ma_period,
            volume_window=self.p.volume_window,
            recent_high_window=self.p.recent_high_window,
        )

        # 寄り後 skip_minutes 分を除外するためのしきい時刻
        base_open = datetime.combine(d.index[0].date(), self.market_open)
        open_cutoff = pd.Timestamp(base_open, tz=d.index.tz) + pd.Timedelta(minutes=self.skip_minutes)

        # 各条件をベクトル化して評価（前バーとの比較に shift を使用）
        cross_up = (d["close"].shift(1) <= d["vwap"].shift(1)) & (d["close"] > d["vwap"])
        vol_surge = d["volume"] >= self.p.volume_factor * d["volume_avg"]
        breakout = d["close"] > d["recent_high"]
        time_ok = d.index >= open_cutoff
        hit = cross_up & vol_surge & breakout & time_ok

        signals: list[Signal] = []
        for ts, row in d[hit].iterrows():
            snap = IndicatorSnapshot(
                price=float(row["close"]),
                vwap=float(row["vwap"]),
                ma=float(row["ma"]),
                volume=float(row["volume"]),
                volume_avg=float(row["volume_avg"]),
                recent_high=float(row["recent_high"]),
            )
            reason = (
                f"VWAP上抜け / 出来高{snap.volume_ratio:.1f}倍 / "
                f"直近高値更新（VWAP乖離 {snap.vwap_diff_pct:+.2f}%）"
            )
            signals.append(
                Signal(
                    symbol=symbol,
                    name=name,
                    type=SignalType.BUY,
                    timestamp=ts.to_pydatetime(),
                    strategy_id=self.strategy_id,
                    indicators=snap,
                    reason=reason,
                )
            )
        return signals
