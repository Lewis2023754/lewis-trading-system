# Lewis Trading System

Autonomous BTC/USDT algorithmic trading infrastructure built in Python, running on Binance testnet and live.

## Bots

| Bot | Strategy | Sessions (UTC) | IST | Backtest |
|---|---|---|---|---|
| **SNAP v2** | Zone reversal | 02:30 & 14:30 | 08:00 & 20:00 | 94.2% WR, $3,202/6mo |
| **STORM** | Peak volatility reversal | 13:30–16:30 | 19:00–22:00 | $6,673/yr, 51.8% WR |
| **Eddy** | AI zone breakout | 02:30 & 14:30 | 08:00 & 20:00 | AI-driven |
| **Bolt** | Zone breakout | 02:30 & 14:30 | 08:00 & 20:00 | Testing |
| **Medic** | Watchdog | Always | Always | — |

## Strategy Overview

### SNAP v2 (Primary Bot)
- Detects zones from session open candle + first opposite-color candle
- Entry: price touches zone boundary then pulls back (reversal/fade)
- SL = zone size (capped at 150pts), TP = SL × 3 (1:3 RR)
- Max 1 flip per session (if SL hit → immediately flip direction)
- Sessions: 4 hours each

### STORM (Best Performing)
- Same reversal logic as SNAP
- Trades exclusively during peak US market hours (13:30–16:30 UTC)
- Highest volume and volatility window — backtested $6,673 profit/year
- 4 sessions per day: 13:30, 14:30, 15:30, 16:30 UTC

### Medic (Watchdog)
- Pre-session health check at 02:15 & 14:15 UTC
- Auto-restarts Eddy and Bolt if crashed
- NEVER auto-restarts SNAP or STORM (manual only)
- 30-minute health checks with Telegram alerts

## Setup

### Requirements
- Python 3.12+
- Binance account (testnet or live API keys)
- Telegram bot token

### Install
```bash
git clone https://github.com/Lewis2023754/lewis-trading-system
cd lewis-trading-system
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

### Environment Variables
```bash
cp .env.example .env
nano .env  # Add your keys
```

### Run Bots
```bash
# Start all bots in separate screen sessions
screen -dmS snap python3 snap.py
screen -dmS storm python3 storm.py
screen -dmS eddy python3 eddy.py
screen -dmS bolt python3 bolt.py
screen -dmS medic python3 medic.py

# Check status
screen -ls
```

### Emergency Restore
```bash
screen -dmS snap python3 snap.py && \
screen -dmS eddy python3 eddy.py && \
screen -dmS bolt python3 bolt.py && \
screen -dmS storm python3 storm.py && \
screen -dmS medic python3 medic.py
```

## Infrastructure

- **VPS**: Hostinger KVM2, Alpine Linux
- **Exchange**: Binance (testnet + live)
- **AI Assistant**: Lewis (OpenClaw + DeepSeek V3 via OpenRouter)
- **Monitoring**: Netdata + Healthchecks.io + Telegram
- **Market Data**: 5-year BTC 5m candle dataset

## Backtesting

Run backtests on historical data:
```bash
python3 snap_backtest.py    # SNAP 6-month backtest
python3 storm_backtest.py   # STORM 1-year backtest
python3 bolt_optimizer.py   # Bolt parameter optimizer
```

## Going Live

1. Set `SPOT_BASE=https://api.binance.com` in `.env`
2. Add real Binance API keys
3. Start with `BASE_QTY=0.001` for 1 week
4. Scale to `BASE_QTY=0.03` after validation

## Disclaimer

This software is for **educational purposes only**. Cryptocurrency trading involves significant financial risk. Never trade more than you can afford to lose. Past backtest performance does not guarantee future results.

## License

MIT License
