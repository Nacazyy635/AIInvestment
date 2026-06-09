"""エグジット（決済）ルール。

保有中の建玉について、そのバーで決済すべきかを判定する純粋関数。
仕様§5.2: 利確 / 損切り / 時間切れ / 大引け強制決済。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from .models import ExitReason, Position


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
      1) 損切り（バー安値が逆指値に触れたら約定したとみなす）
      2) 利確（バー高値が利確値に触れたら約定したとみなす）
      3) 大引け強制決済（forced_close_ts 以降）
      4) 時間切れ（保有が time_exit_minutes 以上）

    同一バー内で損切り・利確の両方に触れた場合は、どちらが先か不明なので
    保守的に「損切り」を優先する（バックテストを甘く見積もらないため）。
    """
    if bar_low <= position.stop_price:
        return ExitReason.STOP_LOSS, position.stop_price
    if bar_high >= position.take_price:
        return ExitReason.TAKE_PROFIT, position.take_price
    if bar_ts >= forced_close_ts:
        return ExitReason.FORCED_CLOSE, bar_close
    if (bar_ts - position.entry_ts).total_seconds() >= time_exit_minutes * 60:
        return ExitReason.TIME_EXIT, bar_close
    return None
