#!/usr/bin/env python3
"""
Eddy Self-Improvement System
Analyzes Eddy's session performance and auto-tunes parameters
Runs after each session and updates eddy_params.json
"""
import json
import os
import csv
import requests
from datetime import datetime, timezone, timedelta

LOG_PATH    = "/root/lewis/lewis.log"
PARAMS_PATH = "/root/lewis/eddy_params.json"
TG_TOKEN    = os.getenv("TG_TOKEN", "")
TG_CHAT     = os.getenv("TG_CHAT", "")

# Default params
DEFAULT_PARAMS = {
    "RISK": 20.0,
    "TRAIL_POINTS": 200.0,
    "version": 1,
    "last_updated": "",
    "total_sessions": 0,
    "total_wins": 0,
    "total_losses": 0,
    "win_streak": 0,
    "loss_streak": 0,
    "notes": "Initial params"
}

def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": f"Eddy Tuner\n{msg}"},
            timeout=10
        )
    except: pass

def load_params():
    if os.path.exists(PARAMS_PATH):
        return json.load(open(PARAMS_PATH))
    return DEFAULT_PARAMS.copy()

def save_params(params):
    params["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    params["version"] = params.get("version", 1) + 1
    json.dump(params, open(PARAMS_PATH, "w"), indent=2)

def parse_log():
    """Parse today's sessions from lewis.log"""
    if not os.path.exists(LOG_PATH):
        return []

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sessions = []
    current = None

    with open(LOG_PATH) as f:
        for line in f:
            if today not in line:
                continue
            if "Session started" in line or "Session over" in line:
                if "started" in line and "MORNING" in line:
                    current = {"name": "MORNING", "wins": 0, "losses": 0, "pnl": 0.0}
                elif "started" in line and "EVENING" in line:
                    current = {"name": "EVENING", "wins": 0, "losses": 0, "pnl": 0.0}
                elif "over" in line and current:
                    # Extract PnL
                    try:
                        pnl_str = line.split("$")[1].split("}")[0]
                        current["pnl"] = float(pnl_str)
                    except: pass
                    sessions.append(current)
                    current = None
            elif current:
                if "WIN" in line:
                    current["wins"] += 1
                    try:
                        pnl = float(line.split("+$")[1].split('"')[0].split("}")[0].strip())
                        current["pnl"] += pnl
                    except: pass
                elif "SL hit" in line:
                    current["losses"] += 1

    return sessions

def analyze_and_tune():
    params = load_params()
    sessions = parse_log()

    if not sessions:
        print("No sessions found today")
        return params

    # Calculate today's performance
    today_wins = sum(s["wins"] for s in sessions)
    today_losses = sum(s["losses"] for s in sessions)
    today_pnl = sum(s["pnl"] for s in sessions)
    today_trades = today_wins + today_losses
    today_wr = round(today_wins / today_trades * 100, 1) if today_trades > 0 else 0

    # Update totals
    params["total_sessions"] += len(sessions)
    params["total_wins"] += today_wins
    params["total_losses"] += today_losses

    # Update streaks
    if today_pnl > 0:
        params["win_streak"] += 1
        params["loss_streak"] = 0
    elif today_pnl < 0:
        params["loss_streak"] += 1
        params["win_streak"] = 0

    old_risk = params["RISK"]
    old_trail = params["TRAIL_POINTS"]

    # ── Auto-tune logic ──────────────────────────────────
    # Win streak 3+ → increase RISK by 10% (max 50)
    if params["win_streak"] >= 3:
        params["RISK"] = min(50.0, round(params["RISK"] * 1.10, 1))
        params["notes"] = f"Win streak {params['win_streak']} — increased RISK"

    # Loss streak 2+ → decrease RISK by 20% (min 10)
    elif params["loss_streak"] >= 2:
        params["RISK"] = max(10.0, round(params["RISK"] * 0.80, 1))
        params["notes"] = f"Loss streak {params['loss_streak']} — decreased RISK"

    # Win rate > 70% → tighten trail points slightly
    if today_wr > 70 and today_trades >= 3:
        params["TRAIL_POINTS"] = max(100.0, round(params["TRAIL_POINTS"] * 0.95, 0))
        params["notes"] += " | Trail tightened"

    # Win rate < 30% → widen trail points
    elif today_wr < 30 and today_trades >= 3:
        params["TRAIL_POINTS"] = min(400.0, round(params["TRAIL_POINTS"] * 1.10, 0))
        params["notes"] += " | Trail widened"

    save_params(params)

    # Report
    report = (
        f"Eddy Auto-Tune Report\n"
        f"Today: {today_wins}W/{today_losses}L WR={today_wr}% PnL=${round(today_pnl,2)}\n"
        f"RISK: ${old_risk} → ${params['RISK']}\n"
        f"TRAIL: {old_trail} → {params['TRAIL_POINTS']}pts\n"
        f"Win streak: {params['win_streak']} | Loss streak: {params['loss_streak']}\n"
        f"Note: {params['notes']}"
    )
    print(report)
    tg(report)

    return params

if __name__ == "__main__":
    print("Running Eddy auto-tune...")
    params = analyze_and_tune()
    print(f"\nCurrent params:")
    print(f"  RISK        = {params['RISK']}")
    print(f"  TRAIL_POINTS = {params['TRAIL_POINTS']}")
    print(f"  Win streak  = {params['win_streak']}")
    print(f"  Loss streak = {params['loss_streak']}")
    print(f"  Version     = {params['version']}")
