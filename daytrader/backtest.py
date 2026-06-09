"""仮想売買バックテスト（Step2）。

最新営業日の1分足を頭から再生し、シグナルで建玉 → エグジット規則で決済、を行い、
完結トレードと損益を SQLite に記録する。

簡易化（次段階で精緻化）:
  - エントリーは「シグナル足の終値」で約定
  - 損切り/利確は「逆指値・利確値ちょうど」で約定（スリッページ未考慮）
  - 手数料・税は未考慮
"""
from __future__ import annotations

import logging
from datetime import datetime, time
from typing import List, Optional

import pandas as pd

from .broker import PaperBroker
from .config import AppConfig
from .exits import check_exit
from .models import ExitReason, Position, Trade
from .monitor import build_feed, build_strategy
from .storage import Storage
from .strategy import _hhmm_to_min

logger = logging.getLogger(__name__)


class SessionBacktester:
    """1営業日・1銘柄のセッションを再生して完結トレードを生成する。"""

    def __init__(self, cfg: AppConfig, broker: PaperBroker):
        self.cfg = cfg
        self.broker = broker
        self.strategy = build_strategy(cfg)
        self.p = cfg.strategy.params
        self.trade = cfg.trade
        self.m_close = _hhmm_to_min(cfg.market.close)

    def run_symbol(self, symbol: str, name: str, df: pd.DataFrame) -> List[Trade]:
        if len(df) < 2:
            return []

        signals = self.strategy.evaluate(symbol, name, df)
        sig_ts = {s.timestamp for s in signals}
        sig_reason = {s.timestamp: s.reason for s in signals}

        day = df.index[-1].date()
        fc_min = self.m_close - self.trade.forced_close_buffer_min
        forced_close_ts = (
            pd.Timestamp(datetime.combine(day, time(0, 0)), tz=df.index.tz)
            + pd.Timedelta(minutes=fc_min)
        ).to_pydatetime()

        position: Optional[Position] = None
        round_trips = 0
        trades: List[Trade] = []

        for ts, row in df.iterrows():
            pyts = ts.to_pydatetime()

            # 1) 建玉があれば、まずこの足でエグジット判定
            if position is not None:
                res = check_exit(
                    position,
                    bar_high=float(row["high"]),
                    bar_low=float(row["low"]),
                    bar_close=float(row["close"]),
                    bar_ts=pyts,
                    time_exit_minutes=self.p.time_exit_minutes,
                    forced_close_ts=forced_close_ts,
                )
                if res is not None:
                    reason, price = res
                    trades.append(self.broker.sell(position, price, pyts, reason.value))
                    position = None
                    round_trips += 1
                    continue  # 決済した足では新規建てしない

            # 2) ノーポジかつ往復上限未満なら、シグナル足で新規建て
            if position is None and round_trips < self.trade.max_round_trips_per_symbol:
                if pyts in sig_ts:
                    entry = float(row["close"])
                    stop = entry * (1.0 - self.p.stop_loss_pct / 100.0)
                    take = entry * (1.0 + self.p.take_profit_pct / 100.0)
                    position = self.broker.buy(
                        symbol, name, self.trade.quantity, entry, pyts,
                        self.strategy.strategy_id, stop, take, sig_reason.get(pyts, ""),
                    )

        # 3) 場の終わりまで持ち越したら最終足で強制決済
        if position is not None:
            last_ts = df.index[-1].to_pydatetime()
            last_close = float(df.iloc[-1]["close"])
            trades.append(
                self.broker.sell(position, last_close, last_ts, ExitReason.FORCED_CLOSE.value)
            )

        return trades


def run_backtest(cfg: AppConfig) -> None:
    """ウォッチリスト全銘柄をバックテストし、SQLiteへ保存して結果を表示する。"""
    feed = build_feed(cfg)
    storage = Storage(cfg.trade.db_path)
    all_trades: List[Trade] = []
    session_date: Optional[str] = None

    for sym in cfg.watchlist:
        try:
            df = feed.get_intraday(sym.symbol)
        except Exception as e:
            logger.error("データ取得失敗 %s: %s", sym.symbol, e)
            continue
        if df.empty:
            logger.info("データなし: %s", sym.symbol)
            continue

        session_date = df.index[-1].date().isoformat()
        bt = SessionBacktester(cfg, PaperBroker())
        trades = bt.run_symbol(sym.symbol, sym.name, df)
        all_trades.extend(trades)
        for t in trades:
            logger.info(
                "取引 %-7s %-8s %s→%s %-12s entry=%8.1f exit=%8.1f 損益=%+8.0f円(%+.2f%%)",
                t.symbol, t.name, t.entry_ts.strftime("%H:%M"), t.exit_ts.strftime("%H:%M"),
                t.reason_close, t.entry_price, t.exit_price, t.pnl, t.pnl_pct,
            )

    if session_date is not None:
        storage.replace_day(session_date, cfg.trade.mode, all_trades)
        logger.info("SQLite保存: %s（%d件, mode=%s）", cfg.trade.db_path, len(all_trades), cfg.trade.mode)
    _print_summary(all_trades, session_date, cfg.trade.mode)
    storage.close()


def _print_summary(trades: List[Trade], session_date: Optional[str], mode: str) -> None:
    n = len(trades)
    wins = [t for t in trades if t.pnl > 0]
    total = sum(t.pnl for t in trades)
    win_rate = (len(wins) / n * 100.0) if n else 0.0
    avg = (total / n) if n else 0.0
    line = "=" * 54
    print("\n" + line)
    print(f" バックテスト結果  {session_date}  mode={mode}")
    print(line)
    print(f" 取引数 : {n}")
    print(f" 勝ち   : {len(wins)}   負け: {n - len(wins)}   勝率: {win_rate:.1f}%")
    print(f" 合計損益: {total:+,.0f} 円   平均: {avg:+,.0f} 円/取引")
    print(line)
    print(" ※手数料・スリッページ未考慮（次段階で反映）")
