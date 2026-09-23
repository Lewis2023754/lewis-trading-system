#!/usr/bin/env python3
"""
Medic - Bot Watchdog
Pre-session checks at 02:15 & 14:15 UTC
Health checks every 30 minutes
Auto-restarts Eddy and Bolt only — NEVER SNAP or STORM
"""
import time, requests, subprocess, logging, os
from datetime import datetime, timezone

TG_TOKEN   = os.getenv("TG_TOKEN", "")
TG_CHAT    = os.getenv("TG_CHAT", "")
LOG_PATH   = "medic.log"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_PATH)])
log = logging.getLogger("Medic")

def tg(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": f"Medic\n{msg}"}, timeout=10)
    except: pass

def check_bot(name, script):
    r = subprocess.run(["pgrep", "-f", script], capture_output=True)
    ok = r.returncode == 0
    return ok, f"{name} OK" if ok else f"{name} DOWN"

def check_openclaw():
    r = subprocess.run(["docker", "ps"], capture_output=True, text=True)
    ok = "openclaw" in r.stdout and "Up" in r.stdout
    return ok, "Lewis OK" if ok else "Lewis DOWN"

def repair_eddy():
    subprocess.run(["pkill", "-f", "eddy.py"], capture_output=True)
    time.sleep(2)
    subprocess.Popen(["screen", "-dmS", "eddy", "python3", "eddy.py"])
    time.sleep(3)
    ok, msg = check_bot("Eddy", "eddy.py")
    log.info(f"Eddy repair: {msg}"); tg(f"Eddy repaired: {msg}")

def repair_bolt():
    subprocess.run(["pkill", "-f", "bolt.py"], capture_output=True)
    time.sleep(2)
    subprocess.Popen(["screen", "-dmS", "bolt", "python3", "bolt.py"])
    time.sleep(3)
    ok, msg = check_bot("Bolt", "bolt.py")
    log.info(f"Bolt repair: {msg}"); tg(f"Bolt repaired: {msg}")

def repair_openclaw():
    subprocess.run(["docker", "compose", "down"], cwd="/root/openclaw", capture_output=True)
    time.sleep(3)
    subprocess.run(["docker", "compose", "up", "-d"], cwd="/root/openclaw", capture_output=True)
    time.sleep(10)
    ok, msg = check_openclaw()
    log.info(f"Lewis repair: {msg}"); tg(f"Lewis repaired: {msg}")

def pre_session_check(session_name):
    snap_ok, snap_msg = check_bot("SNAP", "snap.py")
    storm_ok, storm_msg = check_bot("STORM", "storm.py")
    eddy_ok, eddy_msg = check_bot("Eddy", "eddy.py")
    lewis_ok, lewis_msg = check_openclaw()
    report = (f"PRE-SESSION CHECK — {session_name}\n"
              f"SNAP: {snap_msg}\nSTORM: {storm_msg}\n"
              f"Eddy: {eddy_msg}\nLewis: {lewis_msg}\n"
              f"Session starts in 15 min")
    tg(report); log.info(f"Pre-session: {snap_msg} | {eddy_msg}")
    if not eddy_ok: repair_eddy()
    if not lewis_ok: repair_openclaw()
    if not snap_ok: tg("SNAP IS DOWN — manual restart required")
    if not storm_ok: tg("STORM IS DOWN — manual restart required")

log.info("Medic starting — Watching SNAP + STORM + Eddy + Bolt + Lewis")
tg("Medic Online\nWatching: SNAP + STORM + Eddy + Bolt + Lewis")

pre_session_sent = {m: False for m in ["MORNING", "EVENING"]}

while True:
    try:
        now = datetime.now(timezone.utc)
        if now.hour == 2 and now.minute == 15:
            if not pre_session_sent["MORNING"]:
                pre_session_check("MORNING"); pre_session_sent["MORNING"] = True
        else:
            pre_session_sent["MORNING"] = False
        if now.hour == 14 and now.minute == 15:
            if not pre_session_sent["EVENING"]:
                pre_session_check("EVENING"); pre_session_sent["EVENING"] = True
        else:
            pre_session_sent["EVENING"] = False
        if now.minute == 0 or now.minute == 30:
            snap_ok, snap_msg = check_bot("SNAP", "snap.py")
            storm_ok, storm_msg = check_bot("STORM", "storm.py")
            eddy_ok, eddy_msg = check_bot("Eddy", "eddy.py")
            bolt_ok, bolt_msg = check_bot("Bolt", "bolt.py")
            lewis_ok, lewis_msg = check_openclaw()
            log.info(f"Health: {snap_msg} | {storm_msg} | {eddy_msg} | {bolt_msg} | {lewis_msg}")
            if not eddy_ok: repair_eddy()
            if not bolt_ok: repair_bolt()
            if not lewis_ok: repair_openclaw()
            if not snap_ok: tg("SNAP DOWN — manual restart required")
            if not storm_ok: tg("STORM DOWN — manual restart required")
        time.sleep(30)
    except KeyboardInterrupt:
        log.info("Medic stopped"); tg("Medic stopped"); break
    except Exception as e:
        log.error(str(e)); time.sleep(30)
