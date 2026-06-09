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

    返すDataFrameは tz-aware な DatetimeIndex と
    columns=[open, high, low, close, volume] を持つこと。
    """

    @abstractmethod
    def get_intraday(self, symbol: str) -> pd.DataFrame:
        """指定銘柄の当日（最新営業日）の分足を返す（監視用）。"""
        raise NotImplementedError

    def get_history(self, symbol: str, interval: str, period_days: int) -> pd.DataFrame:
        """複数営業日にまたがる分足を返す（バックテスト用）。対応しない実装もある。"""
        raise NotImplementedError

    def get_daily(self, symbol: str, period_days: int = 120) -> pd.DataFrame:
        """日足を返す（トレンド判定用）。対応しない実装もある。"""
        raise NotImplementedError


class YFinanceFeed(DataFeed):
    """yfinance による遅延データ取得（Mac・開発／Step1-2用）。

    注意: 約15〜20分遅延。yfinanceの分足は取得期間に制約がある
    （1m≈直近7日 / 5m・2m≈直近60日）。本番は kabu のリアルタイムに差し替える。
    """

    def __init__(self, interval: str = "1m", lookback_days: int = 2, tz: str = "Asia/Tokyo"):
        self.interval = interval
        self.lookback_days = lookback_days
        self.tz = tz

    def get_history(self, symbol: str, interval: str, period_days: int) -> pd.DataFrame:
        import yfinance as yf

        period = f"{max(period_days, 1)}d"
        df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=False)
        if df.empty:
            logger.warning("データ取得結果が空: %s", symbol)
            return pd.DataFrame(columns=REQUIRED_COLUMNS)

        df = df.rename(columns=str.lower)[REQUIRED_COLUMNS]
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df.index = df.index.tz_convert(self.tz)
        return df

    def get_intraday(self, symbol: str) -> pd.DataFrame:
        df = self.get_history(symbol, self.interval, max(self.lookback_days, 1))
        if df.empty:
            return df
        # 最新の1営業日だけを使う（VWAPは日次でリセットするため）
        last_day = df.index[-1].date()
        return df[df.index.date == last_day]

    def get_daily(self, symbol: str, period_days: int = 120) -> pd.DataFrame:
        import yfinance as yf

        df = yf.Ticker(symbol).history(period=f"{period_days}d", interval="1d", auto_adjust=False)
        if df.empty:
            logger.warning("日足が空: %s", symbol)
            return pd.DataFrame(columns=REQUIRED_COLUMNS)
        df = df.rename(columns=str.lower)[REQUIRED_COLUMNS]
        if df.index.tz is not None:
            df.index = df.index.tz_convert(self.tz)
        return df
