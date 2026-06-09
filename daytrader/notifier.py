"""通知（アダプタ）。

`Notifier` 抽象に対し、Console（開発・フォールバック）と Discord（本番）を実装。
Discord Webhook URL が無ければ自動でコンソール出力に切り替わる。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

import requests

from .models import Signal

logger = logging.getLogger(__name__)


def format_signal(signal: Signal) -> str:
    """シグナルを人が読めるテキストに整形（Console/Discord共通）。"""
    i = signal.indicators
    return (
        f"🔔 シグナル: {signal.name}（{signal.symbol}）\n"
        f"種別: {signal.type.value}（買い候補・通知のみ／発注なし）\n"
        f"時刻: {signal.timestamp:%Y-%m-%d %H:%M}\n"
        f"価格: {i.price:,.1f}（VWAP {i.vwap:,.1f} / 乖離 {i.vwap_diff_pct:+.2f}%）\n"
        f"出来高: {i.volume:,.0f}（平均比 {i.volume_ratio:.1f}倍）\n"
        f"100株コスト: 約¥{i.price * 100:,.0f}\n"
        f"理由: {signal.reason}"
    )


class Notifier(ABC):
    @abstractmethod
    def send(self, signal: Signal) -> None:
        raise NotImplementedError


class ConsoleNotifier(Notifier):
    """標準出力に表示（開発・Discord未設定時のフォールバック）。"""

    def send(self, signal: Signal) -> None:
        print("\n" + "-" * 48 + "\n" + format_signal(signal) + "\n" + "-" * 48)


class DiscordNotifier(Notifier):
    """Discord Webhook に送信（本番）。"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, signal: Signal) -> None:
        try:
            resp = requests.post(
                self.webhook_url, json={"content": format_signal(signal)}, timeout=10
            )
            resp.raise_for_status()
        except Exception as e:  # 通知失敗で本体を止めない
            logger.error("Discord通知に失敗: %s", e)


def build_notifier(provider: str, webhook_url: Optional[str]) -> Notifier:
    """設定に応じて適切な Notifier を生成する。"""
    if provider in ("auto", "discord") and webhook_url:
        logger.info("通知先: Discord")
        return DiscordNotifier(webhook_url)
    logger.info("通知先: コンソール（Discord Webhook未設定）")
    return ConsoleNotifier()
