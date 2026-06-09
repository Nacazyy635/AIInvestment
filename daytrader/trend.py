"""日足トレンド判定（強い株 / 弱い株）。

順張り戦略なのにトレンドの向きを見ないと、上昇株を“下抜け”で売って踏み上げ、
下落株を“上抜け”で買って戻り売りに沈む。そこで日足の強弱で方向を絞る。
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from .models import Side


def trend_side(daily: pd.DataFrame, session_date: date, ma_days: int) -> Optional[Side]:
    """session_date の「前日まで」の日足で強弱を判定する（先読み回避）。

    - 直近終値 > ma_days日移動平均 → 強い → Side.LONG（買いのみ許可）
    - 直近終値 < 移動平均             → 弱い → Side.SHORT（売りのみ許可）
    - データ不足で判定不能            → None（その日は見送り）
    """
    if daily is None or daily.empty:
        return None
    prior = daily[daily.index.date < session_date]
    if len(prior) < ma_days:
        return None
    sma = prior["close"].tail(ma_days).mean()
    last_close = prior["close"].iloc[-1]
    return Side.LONG if last_close > sma else Side.SHORT
