"""売買戦略（シグナル判定）。

`Strategy` 抽象に対し、2つの戦略を実装：
  - VwapBreakoutStrategy : 順張り（VWAP上抜けで買い / 下抜けで売り）
  - VwapReversionStrategy: 逆張り（VWAPから下乖離で押し目買い / 上乖離で戻り売り）
`config.yaml` の strategy.name で切り替える（仕様§5.2）。
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
    """新規エントリーを許可する時間帯の真偽マスク（寄り直後・引け間際を除外）。"""
    mins = pd.Series(index.hour * 60 + index.minute, index=index)
    morning = (mins >= open_min + skip_open) & (mins <= morning_close_min)
    afternoon = (mins >= afternoon_open_min + skip_open) & (mins <= close_min - skip_close)
    return morning | afternoon


def _build_signals(symbol, name, d, hit, side, strategy_id, label) -> List[Signal]:
    out: List[Signal] = []
    for ts, row in d[hit].iterrows():
        snap = IndicatorSnapshot(
            price=float(row["close"]), vwap=float(row["vwap"]), ma=float(row["ma"]),
            volume=float(row["volume"]), volume_avg=float(row["volume_avg"]),
            recent_high=float(row["recent_high"]),
        )
        reason = f"{label}（VWAP乖離{snap.vwap_diff_pct:+.2f}% / 出来高{snap.volume_ratio:.1f}倍）"
        out.append(Signal(
            symbol=symbol, name=name, side=side, timestamp=ts.to_pydatetime(),
            strategy_id=strategy_id, indicators=snap, reason=reason,
        ))
    return out


class Strategy(ABC):
    strategy_id: str

    @abstractmethod
    def evaluate(self, symbol: str, name: str, df: pd.DataFrame) -> List[Signal]:
        raise NotImplementedError


class _VwapBase(Strategy):
    """VWAP系の共通処理（時間帯フィルタ・出来高条件・指標計算）。"""

    def __init__(self, params: StrategyParams, market: MarketConfig):
        self.p = params
        self.m_open = _hhmm_to_min(market.open)
        self.m_mclose = _hhmm_to_min(market.morning_close)
        self.m_aopen = _hhmm_to_min(market.afternoon_open)
        self.m_close = _hhmm_to_min(market.close)

    def _prep(self, df: pd.DataFrame):
        d = add_indicators(
            df, ma_period=self.p.ma_period, volume_window=self.p.volume_window,
            recent_high_window=self.p.recent_high_window,
        )
        time_ok = allowed_entry_mask(
            d.index, open_min=self.m_open, morning_close_min=self.m_mclose,
            afternoon_open_min=self.m_aopen, close_min=self.m_close,
            skip_open=self.p.skip_minutes_after_open, skip_close=self.p.skip_minutes_before_close,
        )
        vol_surge = d["volume"] >= self.p.volume_factor * d["volume_avg"]
        return d, time_ok, vol_surge


class VwapBreakoutStrategy(_VwapBase):
    """順張り：VWAP上抜け＋直近高値更新で買い／下抜け＋直近安値更新で売り。"""
    strategy_id = "vwap_breakout"

    def evaluate(self, symbol, name, df):
        if len(df) < 2:
            return []
        d, time_ok, vol_surge = self._prep(df)
        margin = self.p.min_vwap_diff_pct / 100.0

        above = d["close"] > d["vwap"] * (1.0 + margin)
        long_hit = above & (~above.shift(1, fill_value=False)) & vol_surge & (d["close"] > d["recent_high"]) & time_ok
        below = d["close"] < d["vwap"] * (1.0 - margin)
        short_hit = below & (~below.shift(1, fill_value=False)) & vol_surge & (d["close"] < d["recent_low"]) & time_ok

        sigs = _build_signals(symbol, name, d, long_hit, Side.LONG, self.strategy_id, "VWAP上抜け+高値更新")
        if self.p.allow_short:
            sigs += _build_signals(symbol, name, d, short_hit, Side.SHORT, self.strategy_id, "VWAP下抜け+安値更新")
        sigs.sort(key=lambda s: s.timestamp)
        return sigs


class VwapReversionStrategy(_VwapBase):
    """逆張り：VWAPから下に乖離→押し目買い／上に乖離→戻り売り（戻りを狙う）。"""
    strategy_id = "vwap_reversion"

    def evaluate(self, symbol, name, df):
        if len(df) < 2:
            return []
        d, time_ok, vol_surge = self._prep(df)
        dev = self.p.reversion_dev_pct / 100.0

        # VWAPから下に乖離した最初の足で買い（戻りを狙う）
        below = d["close"] < d["vwap"] * (1.0 - dev)
        long_hit = below & (~below.shift(1, fill_value=False)) & vol_surge & time_ok
        # 上に乖離した最初の足で売り
        above = d["close"] > d["vwap"] * (1.0 + dev)
        short_hit = above & (~above.shift(1, fill_value=False)) & vol_surge & time_ok

        sigs = _build_signals(symbol, name, d, long_hit, Side.LONG, self.strategy_id, "押し目買い(VWAP下乖離)")
        if self.p.allow_short:
            sigs += _build_signals(symbol, name, d, short_hit, Side.SHORT, self.strategy_id, "戻り売り(VWAP上乖離)")
        sigs.sort(key=lambda s: s.timestamp)
        return sigs


def make_strategy(name: str, params: StrategyParams, market: MarketConfig) -> Strategy:
    """strategy.name から戦略インスタンスを生成。"""
    if name == "vwap_reversion":
        return VwapReversionStrategy(params, market)
    return VwapBreakoutStrategy(params, market)
