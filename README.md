# 自動デイトレ・短期投資システム

ルールベースの自動売買エンジン ＋ AI補助（仕様は [`自動デイトレシステム_仕様書.md`](自動デイトレシステム_仕様書.md)）。

- **開発＝Mac**（M1）／**運用＝Windowsデスクトップ**（kabuステーションAPI）
- 証券：三菱UFJ eスマート証券（旧auカブコム）
- 現在：**Step 1（監視システム）** … データ取得→指標計算→シグナル判定→通知。**発注はしない。**

## セットアップ（Mac）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # Discord通知を使うなら .env にURLを設定（任意）
```

## 実行

```bash
python run.py --mode once     # 最新営業日を1回スキャン（動作確認向き）
python run.py --mode loop     # poll_interval_sec ごとに繰り返し監視
python run.py --backtest      # 最新営業日を仮想売買でバックテスト→SQLite記録（Step2）
python run.py --test-notify   # 通知設定の確認（サンプルを1件送る）
```

監視銘柄・戦略パラメータは [`config.yaml`](config.yaml) で調整（コードは変更不要）。

## テスト

```bash
python -m unittest discover -s tests -t .
```

## 構成

| パス | 役割 |
|------|------|
| `run.py` | CLIエントリーポイント |
| `config.yaml` / `.env` | 設定 / 秘密情報（`.env`はgit管理外） |
| `daytrader/config.py` | 設定の読み込み・検証（pydantic） |
| `daytrader/models.py` | データ構造（`Signal` 等） |
| `daytrader/datafeed.py` | `DataFeed`抽象 + `YFinanceFeed` |
| `daytrader/indicators.py` | VWAP/MA/出来高などの計算（純粋関数） |
| `daytrader/strategy.py` | `Strategy`抽象 + VWAP順張り |
| `daytrader/notifier.py` | `Notifier`抽象 + Console/Discord |
| `daytrader/monitor.py` | 監視ループ（オーケストレーション） |
| `daytrader/broker.py` | `Broker`抽象 + PaperBroker（仮想約定） |
| `daytrader/exits.py` | エグジット判定（利確/損切り/時間切れ/引け） |
| `daytrader/backtest.py` | セッション再生の仮想売買バックテスト |
| `daytrader/storage.py` | SQLite永続化（trades） |

> ⚠️ 本ソフトは技術検証用。投資判断・取引は自己責任で。投資助言ではありません。
