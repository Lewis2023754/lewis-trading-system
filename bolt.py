#!/usr/bin/env python3
"""
BOLT - Zone Chase Strategy
Sessions: 02:30 & 14:30 UTC (08:00 & 20:00 IST)
Reference candle: closes at session time
SL: fixed 3.79pts (experimental)
TP: entry +/- 500pts
Max 3 entries per session
Note: Backtest showed losses — strategy under review
"""
import os
ZONE_OFFSET = 100.0
TP_POINTS   = 500.0
MAX_ENTRIES = 3
BASE_QTY    = 0.03
API_KEY     = os.getenv("API_KEY", "")
SECRET_KEY  = os.getenv("SECRET_KEY", "")
TG_TOKEN    = os.getenv("TG_TOKEN", "")
TG_CHAT     = os.getenv("TG_CHAT", "")
SESSIONS = [
    {"name": "MORNING", "hour": 2,  "minute": 30},
    {"name": "EVENING", "hour": 14, "minute": 30},
]
