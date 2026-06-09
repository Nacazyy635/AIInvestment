"""起動エントリーポイント（CLI）。

    python run.py            # config.yaml の mode で実行
    python run.py --mode once
    python run.py --mode loop
"""
from __future__ import annotations

import argparse
import logging

from daytrader.config import load_config
from daytrader.monitor import Monitor, build_feed, build_strategy
from daytrader.notifier import build_notifier


def main() -> None:
    parser = argparse.ArgumentParser(description="自動デイトレ監視システム (Step1)")
    parser.add_argument("-c", "--config", default="config.yaml", help="設定ファイル")
    parser.add_argument("--mode", choices=["once", "loop"], help="config.yamlのmodeを上書き")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    cfg = load_config(args.config)
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
