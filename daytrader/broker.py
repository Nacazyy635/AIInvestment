"""ブローカー（アダプタ）。

`Broker` 抽象に対し、Step2では `PaperBroker`（仮想約定）を実装。
本番では同じインターフェースで `KabuBroker` を実装し、上位（バックテスト/監視）の
コードを変えずに実発注へ差し替える。買い・売り（信用）両対応。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional

from .models import Position, Side, Trade


class Broker(ABC):
    @abstractmethod
    def open(
        self, side: Side, symbol: str, name: str, qty: int, price: float, ts: datetime,
        strategy_id: str, stop_price: float, take_price: float, reason_open: str,
    ) -> Position:
        raise NotImplementedError

    @abstractmethod
    def close(
        self, position: Position, price: float, ts: datetime,
        reason_close: str, commission: float = 0.0,
    ) -> Trade:
        raise NotImplementedError


class PaperBroker(Broker):
    """仮想ブローカー：実発注せず、約定をシミュレートする（Step2）。"""

    def __init__(self) -> None:
        self.positions: Dict[str, Position] = {}

    def open(
        self, side: Side, symbol: str, name: str, qty: int, price: float, ts: datetime,
        strategy_id: str, stop_price: float, take_price: float, reason_open: str,
    ) -> Position:
        pos = Position(
            symbol=symbol, name=name, side=side, qty=qty, entry_ts=ts, entry_price=price,
            stop_price=stop_price, take_price=take_price,
            strategy_id=strategy_id, reason_open=reason_open,
        )
        self.positions[symbol] = pos
        return pos

    def close(
        self, position: Position, price: float, ts: datetime,
        reason_close: str, commission: float = 0.0,
    ) -> Trade:
        self.positions.pop(position.symbol, None)
        return Trade(
            symbol=position.symbol, name=position.name, strategy_id=position.strategy_id,
            side=position.side, qty=position.qty,
            entry_ts=position.entry_ts, entry_price=position.entry_price,
            exit_ts=ts, exit_price=price,
            reason_open=position.reason_open, reason_close=reason_close,
            commission=commission,
        )

    def get_position(self, symbol: str) -> Optional[Position]:
        return self.positions.get(symbol)
