"""監視のオーケストレーション。

データ取得 → 指標計算＆シグナル判定 → 通知、の流れをまとめる。
各部品（feed / strategy / notifier）は抽象型で受け取るため、
実装の差し替え（yfinance→kabu 等）に強い。
"""
from __future__ import annotations

import logging
import time as time_mod
from datetime import time

from .config import AppConfig
from .datafeed import DataFeed, YFinanceFeed
from .notifier import Notifier, build_notifier
from .strategy import Strategy, VwapBreakoutStrategy

logger = logging.getLogger(__name__)


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def build_feed(cfg: AppConfig) -> DataFeed:
    return YFinanceFeed(
        interval=cfg.datafeed.interval,
        lookback_days=cfg.datafeed.lookback_days,
        tz=cfg.market.timezone,
    )


def build_strategy(cfg: AppConfig) -> Strategy:
    return VwapBreakoutStrategy(
        params=cfg.strategy.params,
        market_open=_parse_hhmm(cfg.market.open),
        skip_minutes=cfg.strategy.params.skip_minutes_after_open,
    )


class Monitor:
    """監視ループ本体。"""

    def __init__(self, cfg: AppConfig, feed: DataFeed, strategy: Strategy, notifier: Notifier):
        self.cfg = cfg
        self.feed = feed
        self.strategy = strategy
        self.notifier = notifier
        self._seen: set[str] = set()  # 通知済みシグナルのキー（重複通知防止）

    def scan_once(self) -> int:
        """全銘柄を1回スキャンし、新規シグナル件数を返す。"""
        new_signals = 0
        for sym in self.cfg.watchlist:
            try:
                df = self.feed.get_intraday(sym.symbol)
            except Exception as e:
                logger.error("データ取得失敗 %s: %s", sym.symbol, e)
                continue

            if df.empty:
                logger.info("データなし: %s（市場時間外/未約定の可能性）", sym.symbol)
                continue

            last = df.iloc[-1]
            logger.info(
                "監視 %-7s %-8s 終値=%8.1f 100株=¥%9.0f 出来高=%10.0f バー数=%d",
                sym.symbol, sym.name, last["close"], last["close"] * 100, last["volume"], len(df),
            )

            for sig in self.strategy.evaluate(sym.symbol, sym.name, df):
                if sig.key in self._seen:
                    continue
                self._seen.add(sig.key)
                self.notifier.send(sig)
                new_signals += 1
        return new_signals

    def run(self) -> None:
        if self.cfg.monitor.mode == "once":
            logger.info("=== once モード: 最新営業日を1回スキャン ===")
            found = self.scan_once()
            logger.info("=== スキャン完了: シグナル %d 件 ===", found)
            return

        interval = self.cfg.monitor.poll_interval_sec
        logger.info("=== loop モード: %d秒ごとにスキャン（Ctrl+Cで停止） ===", interval)
        while True:
            try:
                self.scan_once()
                time_mod.sleep(interval)
            except KeyboardInterrupt:
                logger.info("停止しました。")
                break
