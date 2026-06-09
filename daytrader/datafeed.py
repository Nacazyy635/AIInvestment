"""市場データ取得（アダプタ）。

`DataFeed` という抽象に対し、今は `YFinanceFeed`（遅延・開発用）を実装。
本番では `KabuFeed` を作って差し替えるだけで、上位ロジックは変更不要。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import pandas as pd

logger = logging.getLogger(__name__)

# DataFeed が返すDataFrameが必ず持つ列
REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


class DataFeed(ABC):
    """市場データ取得の抽象インターフェース。

    実装は、tz-aware な DatetimeIndex と
    columns=[open, high, low, close, volume] を持つ1分足DataFrameを返すこと。
    """

    @abstractmethod
    def get_intraday(self, symbol: str) -> pd.DataFrame:
        """指定銘柄の当日（最新営業日）の分足を返す。"""
        raise NotImplementedError


class YFinanceFeed(DataFeed):
    """yfinance による遅延データ取得（Mac・開発／Step1用）。

    注意: 約15〜20分遅延。エントリー精度の検証は本番データで行う（仕様§5.1）。
    """

    def __init__(self, interval: str = "1m", lookback_days: int = 2, tz: str = "Asia/Tokyo"):
        self.interval = interval
        self.lookback_days = lookback_days
        self.tz = tz

    def get_intraday(self, symbol: str) -> pd.DataFrame:
        import yfinance as yf

        period = f"{max(self.lookback_days, 1)}d"
        df = yf.Ticker(symbol).history(period=period, interval=self.interval, auto_adjust=False)
        if df.empty:
            logger.warning("データ取得結果が空: %s", symbol)
            return pd.DataFrame(columns=REQUIRED_COLUMNS)

        # 列名を小文字化し必要列だけに絞る
        df = df.rename(columns=str.lower)[REQUIRED_COLUMNS]

        # タイムゾーンを市場時間（東京）へ統一
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df.index = df.index.tz_convert(self.tz)

        # 最新の1営業日だけを使う（VWAPは日次でリセットするため）
        last_day = df.index[-1].date()
        df = df[df.index.date == last_day]
        return df
