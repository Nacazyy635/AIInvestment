"""設定の読み込みと検証。

config.yaml（挙動の設定）と .env（秘密情報）を分離し、
pydantic で型・既定値・バリデーションを一元管理する。
不正な設定は起動時に例外で弾ける＝トレード中の事故を減らす。
"""
import os
from pathlib import Path
from typing import List, Literal, Optional, Union

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class SymbolConfig(BaseModel):
    symbol: str
    name: str = ""


class DataFeedConfig(BaseModel):
    provider: Literal["yfinance"] = "yfinance"
    interval: str = "1m"
    lookback_days: int = 2


class StrategyParams(BaseModel):
    volume_factor: float = 1.5
    volume_window: int = 20
    recent_high_window: int = 20
    skip_minutes_after_open: int = 5       # 寄り付き直後（前場・後場とも）を除外する分数
    skip_minutes_before_close: int = 30    # 大引け前を除外する分数（強制決済までの猶予）
    min_vwap_diff_pct: float = 0.1         # VWAPからの最低乖離率(%)。微小なダマシ上抜けを除外
    ma_period: int = 25
    # --- エグジット（Step2） ---
    take_profit_pct: float = 0.8           # 利確 +0.8%
    stop_loss_pct: float = 0.5             # 損切り -0.5%
    time_exit_minutes: int = 30            # 保有30分で時間切れ


class StrategyConfig(BaseModel):
    name: str = "vwap_breakout"
    params: StrategyParams = Field(default_factory=StrategyParams)


class MarketConfig(BaseModel):
    timezone: str = "Asia/Tokyo"
    open: str = "09:00"
    morning_close: str = "11:30"
    afternoon_open: str = "12:30"
    close: str = "15:30"


class MonitorConfig(BaseModel):
    poll_interval_sec: int = 30
    mode: Literal["once", "loop"] = "once"


class NotifyConfig(BaseModel):
    provider: Literal["auto", "discord", "console"] = "auto"


class TradeConfig(BaseModel):
    """仮想売買・約定の設定（Step2）。"""
    mode: Literal["PAPER", "LIVE"] = "PAPER"        # 仮想 / 実売買（実売買はまだ使わない）
    quantity: int = 100                             # 1回の発注株数（単元=100株）
    max_round_trips_per_symbol: int = 1             # 同一銘柄1日1往復（差金決済規制）
    forced_close_buffer_min: int = 5                # 大引けの何分前に強制決済するか
    db_path: str = "data/daytrader.db"              # SQLite（gitignore対象）


class AppConfig(BaseModel):
    """アプリ全体の設定。"""
    watchlist: List[SymbolConfig]
    datafeed: DataFeedConfig = Field(default_factory=DataFeedConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    market: MarketConfig = Field(default_factory=MarketConfig)
    monitor: MonitorConfig = Field(default_factory=MonitorConfig)
    notify: NotifyConfig = Field(default_factory=NotifyConfig)
    trade: TradeConfig = Field(default_factory=TradeConfig)

    # .env 由来（設定ファイルには書かない秘密情報）
    discord_webhook_url: Optional[str] = None
    anthropic_api_key: Optional[str] = None


def load_config(path: Union[str, Path] = "config.yaml") -> AppConfig:
    """config.yaml + .env を読み込み、検証済みの AppConfig を返す。"""
    load_dotenv()  # .env を環境変数へ取り込む
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cfg = AppConfig(**raw)
    cfg.discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL") or None
    cfg.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY") or None
    return cfg
