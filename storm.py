#!/usr/bin/env python3
"""
STORM - Peak Volatility Reversal Strategy
Sessions: 13:30, 14:30, 15:30, 16:30 UTC (19:00-22:00 IST)
Logic: SNAP reversal in highest volume hours
SL=150pts | RR=1:3 | Max 1 flip
Backtest: $6,673 profit / 51.8% WR over 1 year
"""
import time, hmac, hashlib, requests, logging, socket, csv, os
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────
API_KEY    = "yjFySXwtVhn1qDsiDu5JeMquCfQcfiNIueOVuyJk8NUj2u1wBfL0eSghbUW1Xar9"
SECRET_KEY = "CQvLaBi7HIu00gS45wIGZa2ce13fZIAf8DOFLNHFNtYk5rXUntdpqE4mMA5yB3st"
SPOT_BASE  = "https://testnet.binance.vision"
REAL_URL   = "https://api.binance.com"
SYMBOL     = "BTCUSDT"
TG_TOKEN   = "8311781962:AAEiKECrLAKwZt-I2y2rLyaKUX0-lrD0rcM"
TG_CHAT    = "6353864470"
BASE_QTY   = 0.03
SL_CAP     = 150.0
RR         = 3
MAX_REENTRY = 1
LOG_PATH   = "/root/lewis/storm.log"
TRADE_LOG  = "/root/lewis/storm_trades.csv"
HC_URL     = "https://hc-ping.com/storm-uuid"  # add healthcheck later
SESSIONS   = [
    {"name": "STORM1", "hour": 13, "minute": 30},
    {"name": "STORM2", "hour": 14, "minute": 30},
    {"name": "STORM3", "hour": 15, "minute": 30},
    {"name": "STORM4", "hour": 16, "minute": 30},
]

# ── Logging ─────────────────────────────────────────────
logging.basicConfig(
    filename=LOG_PATH, level=logging.INFO,
    format="%(asctime)s %(message)s"
)
log = logging.getLogger()

# ── Force IPv4 ──────────────────────────────────────────
_orig = socket.getaddrinfo
def _ipv4(h, p, f=0, t=0, pr=0, fl=0):
    return _orig(h, p, socket.AF_INET, t, pr, fl)
socket.getaddrinfo = _ipv4

# ── Telegram ────────────────────────────────────────────
def tg(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": f"STORM\n{msg}"},
            timeout=10
        )
    except Exception as e:
        log.error(f"TG error: {e}")

# ── Trade log ────────────────────────────────────────────
def log_trade(sess, dr, entry, sl, tp, qty, result, pnl, entries):
    try:
        exists = os.path.exists(TRADE_LOG)
        with open(TRADE_LOG, "a", newline="") as f:
            import csv as _csv
            w = _csv.writer(f)
            if not exists:
                w.writerow(["date","session","dir","entry","sl","tp","qty","result","pnl","entries"])
            w.writerow([
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                sess, dr, round(entry,2), round(sl,2), round(tp,2),
                qty, result, round(pnl,2), entries
            ])
    except Exception as e:
        log.error(f"Trade log error: {e}")

# ── Binance helpers ──────────────────────────────────────
def sign(params):
    q = "&".join([f"{k}={v}" for k,v in params.items()])
    sig = hmac.new(SECRET_KEY.encode(), q.encode(), hashlib.sha256).hexdigest()
    return q + "&signature=" + sig

def place_order(side, qty):
    try:
        ts = int(time.time()*1000)
        p = {"symbol":SYMBOL,"side":side,"type":"MARKET","quantity":round(qty,3),"timestamp":ts}
        r = requests.post(
            f"{SPOT_BASE}/api/v3/order",
            headers={"X-MBX-APIKEY": API_KEY},
            data=sign(p), timeout=10
        )
        return r.json()
    except Exception as e:
        log.error(f"Order error: {e}")
        return {}

def get_price():
    r = requests.get(f"{REAL_URL}/api/v3/ticker/bookTicker", params={"symbol":SYMBOL}, timeout=5)
    d = r.json()
    return float(d["askPrice"]), float(d["bidPrice"])

def get_klines():
    now_ms = int(time.time()*1000)
    r = requests.get(f"{REAL_URL}/api/v3/klines",
        params={"symbol":SYMBOL,"interval":"5m","limit":50}, timeout=10)
    return [{"open_time":int(k[0]),"open":float(k[1]),"high":float(k[2]),
             "low":float(k[3]),"close":float(k[4])}
            for k in r.json() if int(k[6]) < now_ms]

# ── Zone detection ───────────────────────────────────────
def session_open_ms(hour, minute):
    now = datetime.now(timezone.utc)
    t = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return int(t.timestamp()*1000)

def find_zone(session_ms, candles):
    idx = next((i for i,c in enumerate(candles) if c["open_time"]==session_ms), None)
    if idx is None: return None
    anchor = "G" if candles[idx]["close"] >= candles[idx]["open"] else "R"
    last_same = idx
    for i in range(idx+1, len(candles)):
        c = candles[i]
        col = "G" if c["close"] >= c["open"] else "R"
        if col == anchor:
            last_same = i
        else:
            zh = max(candles[last_same]["high"], c["high"])
            zl = min(candles[last_same]["low"], c["low"])
            if zh < 1000 or zl < 1000 or zh-zl > 5000: return None
            return {"high":round(zh,2),"low":round(zl,2),"size":round(zh-zl,2)}
    return None

# ── Session state ────────────────────────────────────────
def new_session(s):
    return {
        "name": s["name"], "hour": s["hour"], "minute": s["minute"],
        "active": False, "zone": None, "trade": False, "dir": None,
        "entry": 0.0, "sl": 0.0, "tp": 0.0, "qty": BASE_QTY,
        "pnl": 0.0, "entries": 0,
        "touched_high": False, "touched_low": False, "over": False,
    }

def reset_session(S):
    S.update({
        "active": True, "zone": None, "trade": False, "dir": None,
        "entry": 0.0, "sl": 0.0, "tp": 0.0, "qty": BASE_QTY,
        "pnl": 0.0, "entries": 0,
        "touched_high": False, "touched_low": False, "over": False,
    })

# ── Main ─────────────────────────────────────────────────
log.info("STORM starting - SL=150 RR=1:3 Sessions=13:30,14:30,15:30,16:30 UTC")
tg("STORM Online\nSL=150 | RR=1:3 | MaxFlip=1\nSessions: 13:30-16:30 UTC (19:00-22:00 IST)\nBacktest: $6,673/yr | WR=51.8%")

sessions = {s["name"]: new_session(s) for s in SESSIONS}

while True:
    try:
        now = datetime.now(timezone.utc)

        for nm, S in sessions.items():
            hr, mn = S["hour"], S["minute"]

            # Session start
            if now.hour == hr and now.minute == mn and not S["active"]:
                reset_session(S)
                log.info(f"[{nm}] Session started")
                tg(f"Session started: {nm}\nWaiting for zone...")

            # Session end (4 hours)
            end_hour = (hr+4) % 24
            if now.hour == end_hour and now.minute == mn and S["active"]:
                if S["trade"]:
                    try:
                        ask, bid = get_price()
                        close_price = bid if S["dir"]=="LONG" else ask
                        pnl = round((close_price-S["entry"])*S["qty"],2) if S["dir"]=="LONG" \
                              else round((S["entry"]-close_price)*S["qty"],2)
                        close_side = "SELL" if S["dir"]=="LONG" else "BUY"
                        place_order(close_side, S["qty"])
                        S["pnl"] += pnl
                        result = "WIN" if pnl>=0 else "LOSS"
                        log_trade(nm, S["dir"], S["entry"], S["sl"], S["tp"],
                                  S["qty"], "TIMEOUT-"+result, pnl, S["entries"])
                        tg(f"Session ended [{nm}]\nTrade closed at timeout\n"
                           f"{S['dir']} Entry: ${S['entry']}\n"
                           f"Close: ${round(close_price,2)}\n"
                           f"PnL: ${pnl}\nSession PnL: ${round(S['pnl'],2)}")
                    except Exception as e:
                        log.error(f"Session end close error: {e}")
                else:
                    tg(f"Session ended [{nm}]\nNo trade\nSession PnL: ${round(S['pnl'],2)}")
                S["active"] = False
                S["over"]   = True
                log.info(f"[{nm}] Session ended PnL=${round(S['pnl'],2)}")

            if not S["active"] or S["over"]:
                continue

            try:
                ask, bid = get_price()
            except Exception as e:
                log.error(f"Price error: {e}")
                time.sleep(5)
                continue

            # Monitor open trade
            if S["trade"]:
                if S["dir"]=="LONG":
                    hit_tp = bid >= S["tp"]
                    hit_sl = bid <= S["sl"]
                else:
                    hit_tp = ask <= S["tp"]
                    hit_sl = ask >= S["sl"]

                if hit_tp:
                    sl_p = min(S["zone"]["size"], SL_CAP)
                    tp_p = round(sl_p*RR, 1)
                    pnl  = round(tp_p*S["qty"], 2)
                    S["pnl"]  += pnl
                    S["trade"] = False
                    S["over"]  = True
                    log_trade(nm, S["dir"], S["entry"], S["sl"], S["tp"],
                              S["qty"], "WIN", pnl, S["entries"])
                    log.info(f"[{nm}] WIN +${pnl}")
                    tg(f"WIN [{nm}]\n{S['dir']}\nEntry: ${S['entry']}\n"
                       f"TP: ${S['tp']}\nPnL: +${pnl}\n"
                       f"Session PnL: ${round(S['pnl'],2)}\nSession done")

                elif hit_sl:
                    sl_p = min(S["zone"]["size"], SL_CAP)
                    pnl  = round(-sl_p*S["qty"], 2)
                    S["pnl"]  += pnl
                    S["trade"] = False
                    close_side = "SELL" if S["dir"]=="LONG" else "BUY"
                    place_order(close_side, S["qty"])
                    log_trade(nm, S["dir"], S["entry"], S["sl"], S["tp"],
                              S["qty"], "LOSS", pnl, S["entries"])
                    log.info(f"[{nm}] SL hit ${pnl} entries={S['entries']}")

                    if S["entries"] >= MAX_REENTRY+1:
                        S["over"] = True
                        tg(f"LOSS [{nm}] Entry #{S['entries']}\n{S['dir']}\n"
                           f"SL hit\nPnL: ${pnl}\n"
                           f"Session PnL: ${round(S['pnl'],2)}\nSession done")
                    else:
                        z = S["zone"]
                        sl_p2 = min(z["size"], SL_CAP)
                        tp_p2 = round(sl_p2*RR, 1)
                        if S["dir"]=="LONG":
                            S["dir"]   = "SHORT"
                            S["entry"] = round(z["high"], 2)
                            S["sl"]    = round(z["high"]+sl_p2, 2)
                            S["tp"]    = round(z["high"]-tp_p2, 2)
                            place_order("SELL", S["qty"])
                        else:
                            S["dir"]   = "LONG"
                            S["entry"] = round(z["low"], 2)
                            S["sl"]    = round(z["low"]-sl_p2, 2)
                            S["tp"]    = round(z["low"]+tp_p2, 2)
                            place_order("BUY", S["qty"])
                        S["trade"]   = True
                        S["entries"] += 1
                        log_trade(nm, S["dir"], S["entry"], S["sl"], S["tp"],
                                  S["qty"], "ENTRY", 0, S["entries"])
                        log.info(f"[{nm}] FLIP to {S['dir']} entry={S['entry']}")
                        tg(f"LOSS [{nm}]\nSL hit | PnL: ${pnl}\n"
                           f"Session PnL: ${round(S['pnl'],2)}\n---\n"
                           f"FLIP #{S['entries']} {S['dir']}\n"
                           f"Entry: ${S['entry']}\nSL: ${S['sl']}\nTP: ${S['tp']}")
                else:
                    log.info(f"[{nm}] {S['dir']} entry={S['entry']} sl={S['sl']} "
                             f"tp={S['tp']} ask={round(ask,2)} bid={round(bid,2)}")
                time.sleep(5)
                continue

            # Find zone
            if not S["zone"]:
                try:
                    candles = get_klines()
                    z = find_zone(session_open_ms(hr, mn), candles)
                    if z:
                        S["zone"] = z
                        sl_p = min(z["size"], SL_CAP)
                        tp_p = round(sl_p*RR, 1)
                        log.info(f"[{nm}] Zone H={z['high']} L={z['low']} size={z['size']}")
                        tg(f"Zone found [{nm}]\n"
                           f"H: ${z['high']} | L: ${z['low']}\n"
                           f"Size: {z['size']}pts\n"
                           f"SL: {sl_p}pts | TP: {tp_p}pts")
                except Exception as e:
                    log.error(f"Zone error: {e}")
                time.sleep(5)
                continue

            # Entry check
            if S["entries"] > MAX_REENTRY and not S["trade"]:
                S["over"] = True
                continue

            z = S["zone"]
            if ask >= z["high"]: S["touched_high"] = True
            if bid <= z["low"]:  S["touched_low"]  = True

            if S["touched_high"] and ask < z["high"] and not S["trade"]:
                sl_p = min(z["size"], SL_CAP)
                tp_p = round(sl_p*RR, 1)
                S["dir"]          = "SHORT"
                S["entry"]        = round(z["high"], 2)
                S["sl"]           = round(z["high"]+sl_p, 2)
                S["tp"]           = round(z["high"]-tp_p, 2)
                S["trade"]        = True
                S["touched_high"] = False
                S["entries"]      += 1
                place_order("SELL", S["qty"])
                log.info(f"[{nm}] SHORT entry={S['entry']} sl={S['sl']} tp={S['tp']} #{S['entries']}")
                tg(f"SHORT [{nm}] Entry #{S['entries']}\n"
                   f"Entry: ${S['entry']}\nSL: ${S['sl']}\nTP: ${S['tp']}\n"
                   f"Qty: {S['qty']} BTC\n"
                   f"Zone: ${z['high']} - ${z['low']}")
                time.sleep(5)
                continue

            if S["touched_low"] and bid > z["low"] and not S["trade"]:
                sl_p = min(z["size"], SL_CAP)
                tp_p = round(sl_p*RR, 1)
                S["dir"]         = "LONG"
                S["entry"]       = round(z["low"], 2)
                S["sl"]          = round(z["low"]-sl_p, 2)
                S["tp"]          = round(z["low"]+tp_p, 2)
                S["trade"]       = True
                S["touched_low"] = False
                S["entries"]     += 1
                place_order("BUY", S["qty"])
                log.info(f"[{nm}] LONG entry={S['entry']} sl={S['sl']} tp={S['tp']} #{S['entries']}")
                tg(f"LONG [{nm}] Entry #{S['entries']}\n"
                   f"Entry: ${S['entry']}\nSL: ${S['sl']}\nTP: ${S['tp']}\n"
                   f"Qty: {S['qty']} BTC\n"
                   f"Zone: ${z['high']} - ${z['low']}")
                time.sleep(5)
                continue

            log.info(f"[{nm}] Ask={round(ask,2)} Bid={round(bid,2)} | "
                     f"H={z['high']} L={z['low']} | "
                     f"TH={S['touched_high']} TL={S['touched_low']}")

        time.sleep(5)

    except KeyboardInterrupt:
        log.info("STORM stopped")
        tg("STORM stopped")
        break
    except Exception as e:
        log.error(f"Loop error: {e}")
        time.sleep(10)
