"""起動エントリーポイント（CLI）。

    python run.py                 # config.yaml の mode で監視
    python run.py --mode once     # 最新営業日を1回スキャン
    python run.py --mode loop     # 繰り返し監視
    python run.py --backtest      # 最新営業日を仮想売買でバックテスト→SQLite記録
    python run.py --test-notify   # 通知設定の確認（サンプルを1件送る）
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime

from daytrader.config import load_config
from daytrader.models import IndicatorSnapshot, Side, Signal
from daytrader.monitor import Monitor, build_feed, build_strategy
from daytrader.notifier import build_notifier


def _sample_signal() -> Signal:
    """通知テスト用のダミーシグナル（発注はしない）。"""
    snap = IndicatorSnapshot(
        price=336.7, vwap=335.0, ma=334.0,
        volume=97800, volume_avg=40000, recent_high=336.0,
    )
    return Signal(
        symbol="7201.T",
        name="日産自動車（通知テスト）",
        side=Side.LONG,
        timestamp=datetime.now().astimezone(),
        strategy_id="vwap_breakout",
        indicators=snap,
        reason="これは通知テストです（発注なし）",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="自動デイトレ監視システム")
    parser.add_argument("-c", "--config", default="config.yaml", help="設定ファイル")
    parser.add_argument("--mode", choices=["once", "loop"], help="config.yamlのmodeを上書き")
    parser.add_argument("--backtest", action="store_true", help="最新営業日を仮想売買でバックテスト")
    parser.add_argument("--test-notify", action="store_true", help="サンプル通知を1件送って設定確認")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    cfg = load_config(args.config)

    if args.test_notify:
        notifier = build_notifier(cfg.notify.provider, cfg.discord_webhook_url)
        logging.info("通知テストを送信します...")
        notifier.send(_sample_signal())
        logging.info("送信完了。Discord設定時は該当チャンネルを確認してください。")
        return

    if args.backtest:
        from daytrader.backtest import run_backtest
        run_backtest(cfg)
        return

    if args.mode:
        cfg.monitor.mode = args.mode

    feed = build_feed(cfg)
    strategy = build_strategy(cfg)
    notifier = build_notifier(cfg.notify.provider, cfg.discord_webhook_url)

    logging.info("戦略: %s", cfg.strategy.name)
    logging.info("監視銘柄: %s", ", ".join(f"{s.name}({s.symbol})" for s in cfg.watchlist))

    Monitor(cfg, feed, strategy, notifier).run()


if __name__ == "__main__":
    main()
