"""売買戦略（シグナル判定）。

`Strategy` 抽象に対し、MVPの `VwapBreakoutStrategy`（VWAP順張り）を実装。
戦略を差し替え可能にしておくことで、将来オープニングレンジ・ブレイク等を
`strategy_id` で追加できる（仕様§5.2）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from .config import MarketConfig, StrategyParams
from .indicators import add_indicators
from .models import IndicatorSnapshot, Signal, SignalType


def _hhmm_to_min(s: str) -> int:
    """'09:00' → 540（その日の0時からの分）。"""
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def allowed_entry_mask(
    index: pd.DatetimeIndex,
    *,
    open_min: int,
    morning_close_min: int,
    afternoon_open_min: int,
    close_min: int,
    skip_open: int,
    skip_close: int,
) -> pd.Series:
    """新規エントリーを許可する時間帯の真偽マスク。

    除外する時間帯:
      - 寄り付き直後（前場・後場とも開始から skip_open 分）
        … 板寄せ由来の価格歪み・高ボラ・指標の未成熟（特にVWAP）
      - 引け間際（大引け前 skip_close 分）
        … 強制決済までに時間が足りず、デイトレとして成立しないため
    """
    mins = pd.Series(index.hour * 60 + index.minute, index=index)
    morning = (mins >= open_min + skip_open) & (mins <= morning_close_min)
    afternoon = (mins >= afternoon_open_min + skip_open) & (mins <= close_min - skip_close)
    return morning | afternoon


class Strategy(ABC):
    strategy_id: str

    @abstractmethod
    def evaluate(self, symbol: str, name: str, df: pd.DataFrame) -> list[Signal]:
        """分足DataFrameを受け取り、当日のエントリー候補を全て返す。"""
        raise NotImplementedError


class VwapBreakoutStrategy(Strategy):
    """VWAP順張り（買いのみ）。仕様§5.2。

    エントリー条件（すべて満たす）:
      1) 終値が「VWAP × (1 + min_vwap_diff_pct%)」を上抜け
         （前バーはしきい値以下 → 現バーが超え。微小なダマシ上抜けを除外）
      2) 出来高増加（現バー出来高 ≥ volume_factor × 出来高移動平均）
      3) 直近高値を更新（終値 > 直近 recent_high_window 本の高値）
      4) 時間帯フィルタ（寄り付き直後・引け間際を除外、前場/後場の両寄りに適用）

    Step1では検出して通知するのみ（発注しない）。
    """
    strategy_id = "vwap_breakout"

    def __init__(self, params: StrategyParams, market: MarketConfig):
        self.p = params
        self.m_open = _hhmm_to_min(market.open)
        self.m_mclose = _hhmm_to_min(market.morning_close)
        self.m_aopen = _hhmm_to_min(market.afternoon_open)
        self.m_close = _hhmm_to_min(market.close)

    def evaluate(self, symbol: str, name: str, df: pd.DataFrame) -> list[Signal]:
        if len(df) < 2:
            return []

        d = add_indicators(
            df,
            ma_period=self.p.ma_period,
            volume_window=self.p.volume_window,
            recent_high_window=self.p.recent_high_window,
        )

        # 条件1: VWAP×(1+最低乖離) を上抜けた最初のバー（= しきい値クロス）
        threshold = d["vwap"] * (1.0 + self.p.min_vwap_diff_pct / 100.0)
        above = d["close"] > threshold
        crossed_up = above & (~above.shift(1, fill_value=False))
        # 条件2,3
        vol_surge = d["volume"] >= self.p.volume_factor * d["volume_avg"]
        breakout = d["close"] > d["recent_high"]
        # 条件4: 時間帯
        time_ok = allowed_entry_mask(
            d.index,
            open_min=self.m_open,
            morning_close_min=self.m_mclose,
            afternoon_open_min=self.m_aopen,
            close_min=self.m_close,
            skip_open=self.p.skip_minutes_after_open,
            skip_close=self.p.skip_minutes_before_close,
        )

        hit = crossed_up & vol_surge & breakout & time_ok

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
                f"VWAP上抜け(+{snap.vwap_diff_pct:.2f}%) / "
                f"出来高{snap.volume_ratio:.1f}倍 / 直近高値更新"
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
