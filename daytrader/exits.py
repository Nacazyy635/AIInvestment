"""エグジット（決済）ルール。

保有中の建玉について、そのバーで決済すべきかを判定する純粋関数。
仕様§5.2: 利確 / 損切り / 時間切れ / 大引け強制決済。買い・売りの両方に対応。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from .models import ExitReason, Position, Side


def check_exit(
    position: Position,
    *,
    bar_high: float,
    bar_low: float,
    bar_close: float,
    bar_ts: datetime,
    time_exit_minutes: int,
    forced_close_ts: datetime,
) -> Optional[Tuple[ExitReason, float]]:
    """決済すべきなら (理由, 約定価格) を返す。不要なら None。

    判定順（重要）:
      1) 損切り  2) 利確  3) 大引け強制決済  4) 時間切れ

    買い建て: 損切り=安値が逆指値以下 / 利確=高値が利確値以上
    売り建て: 損切り=高値が逆指値以上 / 利確=安値が利確値以下
    同一バーで損切り・利確の両方に触れた場合は、保守的に「損切り」を優先する。
    """
    if position.side == Side.LONG:
        if bar_low <= position.stop_price:
            return ExitReason.STOP_LOSS, position.stop_price
        if bar_high >= position.take_price:
            return ExitReason.TAKE_PROFIT, position.take_price
    else:  # SHORT
        if bar_high >= position.stop_price:
            return ExitReason.STOP_LOSS, position.stop_price
        if bar_low <= position.take_price:
            return ExitReason.TAKE_PROFIT, position.take_price

    if bar_ts >= forced_close_ts:
        return ExitReason.FORCED_CLOSE, bar_close
    if (bar_ts - position.entry_ts).total_seconds() >= time_exit_minutes * 60:
        return ExitReason.TIME_EXIT, bar_close
    return None
