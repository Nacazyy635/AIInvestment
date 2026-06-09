"""仮想売買バックテスト（Step2）。

最新の数営業日（複数日）の分足を取得し、日ごとにセッションを再生して
「シグナルで建玉 → エグジット規則で決済」を行い、完結トレードと損益を
SQLite に記録・集計する。

リアルさのための反映:
  - ポジションは円ベースでサイジング（target_position_yen に近い100株単位）
  - スリッページを約定価格に反映（買いは高く、売りは安く約定）
  - 手数料（commission_bps）を往復で控除

残る簡易化（次段階）:
  - エントリーは「シグナル足の終値」、損切り/利確は「指値ちょうど」を基準に約定
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, time
from typing import List, Optional

import pandas as pd

from .broker import PaperBroker
from .config import AppConfig
from .datafeed import YFinanceFeed
from .exits import check_exit
from .models import ExitReason, Position, Trade
from .monitor import build_strategy
from .sizing import position_size
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
        self.slip = cfg.trade.slippage_bps / 10000.0
        self.comm = cfg.trade.commission_bps / 10000.0

    def _commission(self, entry_price: float, exit_price: float, qty: int) -> float:
        return (entry_price * qty + exit_price * qty) * self.comm

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
                    reason, exit_price = res
                    exit_fill = exit_price * (1.0 - self.slip)  # 売りは安く約定
                    commission = self._commission(position.entry_price, exit_fill, position.qty)
                    trades.append(self.broker.sell(position, exit_fill, pyts, reason.value, commission))
                    position = None
                    round_trips += 1
                    continue  # 決済した足では新規建てしない

            # 2) ノーポジかつ往復上限未満なら、シグナル足で円ベースに建てる
            if position is None and round_trips < self.trade.max_round_trips_per_symbol and pyts in sig_ts:
                raw = float(row["close"])
                shares = position_size(raw, self.trade.target_position_yen, self.trade.max_position_yen)
                if shares > 0:
                    entry_fill = raw * (1.0 + self.slip)  # 買いは高く約定
                    stop = entry_fill * (1.0 - self.p.stop_loss_pct / 100.0)
                    take = entry_fill * (1.0 + self.p.take_profit_pct / 100.0)
                    position = self.broker.buy(
                        symbol, name, shares, entry_fill, pyts,
                        self.strategy.strategy_id, stop, take, sig_reason.get(pyts, ""),
                    )

        # 3) 場の終わりまで持ち越したら最終足で強制決済
        if position is not None:
            last_ts = df.index[-1].to_pydatetime()
            exit_fill = float(df.iloc[-1]["close"]) * (1.0 - self.slip)
            commission = self._commission(position.entry_price, exit_fill, position.qty)
            trades.append(
                self.broker.sell(position, exit_fill, last_ts, ExitReason.FORCED_CLOSE.value, commission)
            )

        return trades


def run_backtest(cfg: AppConfig) -> None:
    """ウォッチリスト全銘柄を複数日バックテストし、SQLiteへ保存して結果を表示する。"""
    bt = cfg.backtest
    feed = YFinanceFeed(interval=bt.interval, lookback_days=bt.days, tz=cfg.market.timezone)
    storage = Storage(cfg.trade.db_path)

    all_trades: List[Trade] = []
    sessions = set()

    for sym in cfg.watchlist:
        try:
            df = feed.get_history(sym.symbol, bt.interval, bt.days)
        except Exception as e:
            logger.error("データ取得失敗 %s: %s", sym.symbol, e)
            continue
        if df.empty:
            logger.info("データなし: %s", sym.symbol)
            continue

        # 日ごとに区切って再生（VWAP等は日次でリセットされる）
        sym_trades: List[Trade] = []
        for day, day_df in df.groupby(df.index.date):
            sessions.add(day)
            engine = SessionBacktester(cfg, PaperBroker())
            sym_trades.extend(engine.run_symbol(sym.symbol, sym.name, day_df))

        all_trades.extend(sym_trades)
        wins = sum(1 for t in sym_trades if t.pnl > 0)
        pnl = sum(t.pnl for t in sym_trades)
        avg_qty = int(sum(t.qty for t in sym_trades) / len(sym_trades)) if sym_trades else 0
        logger.info(
            "%-7s %-8s 取引%3d 勝ち%3d 損益%+10.0f円 (平均%4d株)",
            sym.symbol, sym.name, len(sym_trades), wins, pnl, avg_qty,
        )

    if all_trades:
        storage.save(cfg.trade.mode, all_trades)
        logger.info("SQLite保存: %s（%d件, mode=%s）", cfg.trade.db_path, len(all_trades), cfg.trade.mode)
    _print_summary(all_trades, sessions, cfg)
    storage.close()


def _print_summary(trades: List[Trade], sessions, cfg: AppConfig) -> None:
    n = len(trades)
    wins = [t for t in trades if t.pnl > 0]
    net = sum(t.pnl for t in trades)
    gross = sum(t.gross_pnl for t in trades)
    commission = sum(t.commission for t in trades)
    win_rate = (len(wins) / n * 100.0) if n else 0.0
    avg = (net / n) if n else 0.0
    gross_win = sum(t.pnl for t in wins)
    gross_loss = -sum(t.pnl for t in trades if t.pnl <= 0)
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    reason_ct = Counter(t.reason_close for t in trades)

    byday_pnl: dict = defaultdict(float)
    byday_n: dict = defaultdict(int)
    for t in trades:
        d = t.entry_ts.date().isoformat()
        byday_pnl[d] += t.pnl
        byday_n[d] += 1

    line = "=" * 62
    print("\n" + line)
    print(f" バックテスト結果   mode={cfg.trade.mode}   1ポジ目安 ¥{cfg.trade.target_position_yen:,}")
    print(f" 対象 {cfg.backtest.days}日（{len(sessions)}営業日）× {len(cfg.watchlist)}銘柄   足={cfg.backtest.interval}")
    print(line)
    print(f" 取引数 : {n}")
    print(f" 勝率   : {win_rate:5.1f}%   （勝ち {len(wins)} / 負け {n - len(wins)}）")
    print(f" 合計損益(ネット): {net:+,.0f} 円    平均: {avg:+,.0f} 円/取引")
    print(f"   内訳: 総損益 {gross:+,.0f} − 手数料 {commission:,.0f}")
    if n:
        pf_str = "∞" if pf == float("inf") else f"{pf:.2f}"
        print(f" PF(総利益/総損失): {pf_str}")
        print(" 決済理由: " + " / ".join(f"{k}={v}" for k, v in reason_ct.most_common()))
    print(line)
    if byday_pnl:
        print(" 日別損益（累計）:")
        cum = 0.0
        for d in sorted(byday_pnl):
            cum += byday_pnl[d]
            print(f"   {d}  取引{byday_n[d]:2d}  損益{byday_pnl[d]:+8.0f}  累計{cum:+9.0f}")
        print(line)
    print(f" ※スリッページ{cfg.trade.slippage_bps:.0f}bps/片側を約定価格に反映・手数料{cfg.trade.commission_bps:.0f}bps。5分足。")
