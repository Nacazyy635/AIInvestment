"""テクニカル指標の計算（純粋関数）。

入出力をDataFrameに限定した副作用のない関数群。
純粋関数なのでユニットテストが書きやすく、戦略から再利用できる。
"""
from __future__ import annotations

import pandas as pd


def typical_price(df: pd.DataFrame) -> pd.Series:
    """代表値 (高値+安値+終値)/3。VWAPの加重に使う。"""
    return (df["high"] + df["low"] + df["close"]) / 3.0


def add_indicators(
    df: pd.DataFrame,
    *,
    ma_period: int,
    volume_window: int,
    recent_high_window: int,
) -> pd.DataFrame:
    """OHLCV に指標列を追加した新しいDataFrameを返す（非破壊）。

    追加列:
      - vwap        : 当日VWAP（出来高加重平均価格）＝ Σ(代表値×出来高)/Σ(出来高)
      - ma          : 終値の単純移動平均
      - volume_avg  : 出来高の移動平均
      - recent_high : 直近 recent_high_window 本（現バーを含めない）の高値
    """
    out = df.copy()

    tp = typical_price(out)
    cum_vol = out["volume"].cumsum()
    # cum_vol が 0 の箇所は NaN にして 0除算を回避
    out["vwap"] = (tp * out["volume"]).cumsum() / cum_vol.where(cum_vol != 0)

    out["ma"] = out["close"].rolling(ma_period, min_periods=1).mean()
    out["volume_avg"] = out["volume"].rolling(volume_window, min_periods=1).mean()

    # shift(1) で現バーを除外してから直近高値をとる＝「ブレイク」を正しく判定
    out["recent_high"] = out["high"].shift(1).rolling(recent_high_window, min_periods=1).max()
    return out
