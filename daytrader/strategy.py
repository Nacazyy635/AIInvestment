"""売買戦略（シグナル判定）。

`Strategy` 抽象に対し、MVPの `VwapBreakoutStrategy`（VWAP順張り・両建て）を実装。
戦略を差し替え可能にしておくことで、将来オープニングレンジ・ブレイク等を
`strategy_id` で追加できる（仕様§5.2）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

import pandas as pd

from .config import MarketConfig, StrategyParams
from .indicators import add_indicators
from .models import IndicatorSnapshot, Side, Signal


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
      - 引け間際（大引け前 skip_close 分）
    """
    mins = pd.Series(index.hour * 60 + index.minute, index=index)
    morning = (mins >= open_min + skip_open) & (mins <= morning_close_min)
    afternoon = (mins >= afternoon_open_min + skip_open) & (mins <= close_min - skip_close)
    return morning | afternoon


class Strategy(ABC):
    strategy_id: str

    @abstractmethod
    def evaluate(self, symbol: str, name: str, df: pd.DataFrame) -> List[Signal]:
        """分足DataFrameを受け取り、当日のエントリー候補を全て返す。"""
        raise NotImplementedError


class VwapBreakoutStrategy(Strategy):
    """VWAP順張り（買い・売りの両建て）。仕様§5.2。

    買い（LONG）エントリー（すべて満たす）:
      1) 終値が VWAP×(1+min%) を上抜け  2) 出来高増加  3) 直近高値を更新  4) 時間帯OK
    売り（SHORT）エントリー（買いの鏡像。allow_short のとき）:
      1) 終値が VWAP×(1-min%) を下抜け  2) 出来高増加  3) 直近安値を更新  4) 時間帯OK

    Step1では検出して通知するのみ。Step2のバックテストで仮想売買する。
    """
    strategy_id = "vwap_breakout"

    def __init__(self, params: StrategyParams, market: MarketConfig):
        self.p = params
        self.m_open = _hhmm_to_min(market.open)
        self.m_mclose = _hhmm_to_min(market.morning_close)
        self.m_aopen = _hhmm_to_min(market.afternoon_open)
        self.m_close = _hhmm_to_min(market.close)

    def evaluate(self, symbol: str, name: str, df: pd.DataFrame) -> List[Signal]:
        if len(df) < 2:
            return []

        d = add_indicators(
            df,
            ma_period=self.p.ma_period,
            volume_window=self.p.volume_window,
            recent_high_window=self.p.recent_high_window,
        )

        time_ok = allowed_entry_mask(
            d.index,
            open_min=self.m_open, morning_close_min=self.m_mclose,
            afternoon_open_min=self.m_aopen, close_min=self.m_close,
            skip_open=self.p.skip_minutes_after_open, skip_close=self.p.skip_minutes_before_close,
        )
        vol_surge = d["volume"] >= self.p.volume_factor * d["volume_avg"]
        margin = self.p.min_vwap_diff_pct / 100.0

        # 買い: VWAP×(1+margin) を上抜け＋直近高値更新
        above = d["close"] > d["vwap"] * (1.0 + margin)
        long_hit = above & (~above.shift(1, fill_value=False)) & vol_surge & (d["close"] > d["recent_high"]) & time_ok

        # 売り: VWAP×(1-margin) を下抜け＋直近安値更新
        below = d["close"] < d["vwap"] * (1.0 - margin)
        short_hit = below & (~below.shift(1, fill_value=False)) & vol_surge & (d["close"] < d["recent_low"]) & time_ok

        signals: List[Signal] = self._make(symbol, name, d, long_hit, Side.LONG)
        if self.p.allow_short:
            signals += self._make(symbol, name, d, short_hit, Side.SHORT)
        signals.sort(key=lambda s: s.timestamp)
        return signals

    def _make(self, symbol: str, name: str, d: pd.DataFrame, hit: pd.Series, side: Side) -> List[Signal]:
        out: List[Signal] = []
        for ts, row in d[hit].iterrows():
            snap = IndicatorSnapshot(
                price=float(row["close"]), vwap=float(row["vwap"]), ma=float(row["ma"]),
                volume=float(row["volume"]), volume_avg=float(row["volume_avg"]),
                recent_high=float(row["recent_high"]),
            )
            if side == Side.LONG:
                reason = f"VWAP上抜け(+{snap.vwap_diff_pct:.2f}%) / 出来高{snap.volume_ratio:.1f}倍 / 直近高値更新"
            else:
                reason = f"VWAP下抜け({snap.vwap_diff_pct:.2f}%) / 出来高{snap.volume_ratio:.1f}倍 / 直近安値更新"
            out.append(Signal(
                symbol=symbol, name=name, side=side, timestamp=ts.to_pydatetime(),
                strategy_id=self.strategy_id, indicators=snap, reason=reason,
            ))
        return out
