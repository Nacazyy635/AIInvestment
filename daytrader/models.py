"""ドメインのデータ構造。

「何を扱うか」を型で固定しておくと、後段（通知・DB保存・AI補助）が
このオブジェクトを受け取るだけで済み、各モジュールの結合が緩くなる。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SignalType(str, Enum):
    """シグナルの種別。MVPは買いのみ。将来 SELL / SHORT を追加。"""
    BUY = "BUY"


class ExitReason(str, Enum):
    """決済理由（Step2）。"""
    TAKE_PROFIT = "TAKE_PROFIT"     # 利確
    STOP_LOSS = "STOP_LOSS"         # 損切り
    TIME_EXIT = "TIME_EXIT"         # 時間切れ
    FORCED_CLOSE = "FORCED_CLOSE"   # 大引け強制決済


@dataclass(frozen=True)
class IndicatorSnapshot:
    """あるバー時点の指標スナップショット（通知・記録用）。"""
    price: float          # 終値
    vwap: float           # 当日VWAP
    ma: float             # 移動平均
    volume: float         # そのバーの出来高
    volume_avg: float     # 出来高移動平均
    recent_high: float    # 直近高値（現バーを含めない）

    @property
    def vwap_diff_pct(self) -> float:
        """VWAPからの乖離率（％）。"""
        if self.vwap == 0:
            return 0.0
        return (self.price - self.vwap) / self.vwap * 100.0

    @property
    def volume_ratio(self) -> float:
        """出来高が平均の何倍か。"""
        if self.volume_avg == 0:
            return 0.0
        return self.volume / self.volume_avg


@dataclass(frozen=True)
class Signal:
    """戦略が検出したエントリー候補。"""
    symbol: str
    name: str
    type: SignalType
    timestamp: datetime
    strategy_id: str
    indicators: IndicatorSnapshot
    reason: str

    @property
    def key(self) -> str:
        """重複通知を防ぐための一意キー（銘柄＋時刻）。"""
        return f"{self.symbol}:{self.timestamp.isoformat()}"


@dataclass
class Position:
    """保有中の建玉（Step2・仮想売買）。"""
    symbol: str
    name: str
    qty: int
    entry_ts: datetime
    entry_price: float       # スリッページ反映後の取得単価
    stop_price: float        # 損切りライン（逆指値）
    take_price: float        # 利確ライン
    strategy_id: str
    reason_open: str


@dataclass(frozen=True)
class Trade:
    """完結した1往復のトレード（損益つき）。

    entry_price / exit_price はスリッページ反映後の約定単価。
    commission は往復の手数料。pnl はそれらを引いた手取り（ネット）損益。
    """
    symbol: str
    name: str
    strategy_id: str
    qty: int
    entry_ts: datetime
    entry_price: float
    exit_ts: datetime
    exit_price: float
    reason_open: str
    reason_close: str
    commission: float = 0.0

    @property
    def gross_pnl(self) -> float:
        """手数料控除前の損益（円）。買い：(決済 - 取得) × 株数。"""
        return (self.exit_price - self.entry_price) * self.qty

    @property
    def pnl(self) -> float:
        """ネット損益（円）＝ 総損益 − 手数料。"""
        return self.gross_pnl - self.commission

    @property
    def pnl_pct(self) -> float:
        """ネット損益率（％、取得代金に対して）。"""
        notional = self.entry_price * self.qty
        if notional == 0:
            return 0.0
        return self.pnl / notional * 100.0
