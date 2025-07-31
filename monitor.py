import time
import threading
import datetime
from config import current_position, kite, SL_PERCENT, TSL_PERCENT
from order_manager import exit_position
from histogram import fetch_histogram
from price_tracker import load_price_track, save_price_track, init_db
from gdrive_sync import upload_file  # ✅ Added for Drive upload

def is_30min_boundary():
    now = datetime.datetime.now()
    return now.minute % 30 == 0 and now.second < 10

def monitor_loop():
    init_db()  # Initialize SQLite DB
    last_sl_tsl_check_minute = -1

    while True:
        try:
            now = datetime.datetime.now()

            if current_position["active"]:
                sym = current_position["symbol"]
                ltp = kite.ltp(f"NFO:{sym}")[f"NFO:{sym}"]["last_price"]

                # ======= SL and TSL checks every 5 minutes =======
                if now.minute % 5 == 0 and now.minute != last_sl_tsl_check_minute:
                    last_sl_tsl_check_minute = now.minute
                    print(f"🛡️ SL/TSL Check @ {now.strftime('%H:%M:%S')} | Price: {ltp}")

                    side = current_position["side"]
                    entry = current_position["entry_price"]
                    stop_loss = current_position["stop_loss"]

                    # Load previous TSL tracking
                    track = load_price_track()
                    if track.get("highest_price") is None:
                        track["highest_price"] = entry
                    if track.get("lowest_price") is None:
                        track["lowest_price"] = entry

                    # LONG logic
                    if side == "LONG":
                        if ltp < entry:
                            if ltp <= stop_loss:
                                print("❌ SL hit (LONG) — Exiting")
                                exit_position()
                                continue
                        else:
                            high = max(track["highest_price"], ltp)
                            save_price_track(high=high)
                            upload_file()
                            tsl = high * (1 - TSL_PERCENT)
                            current_position["trailing_sl"] = tsl
                            print(f"🔼 TSL (LONG): {tsl:.2f} | High: {high:.2f} | LTP: {ltp}")
                            if ltp <= tsl:
                                print("❌ TSL hit (LONG) — Exiting")
                                exit_position()
                                continue

                    # SHORT logic
                    elif side == "SHORT":
                        if ltp > entry:
                            if ltp >= stop_loss:
                                print("❌ SL hit (SHORT) — Exiting")
                                exit_position()
                                continue
                        else:
                            low = min(track["lowest_price"], ltp)
                            save_price_track(low=low)
                            upload_file()
                            tsl = low * (1 + TSL_PERCENT)
                            current_position["trailing_sl"] = tsl
                            print(f"🔽 TSL (SHORT): {tsl:.2f} | Low: {low:.2f} | LTP: {ltp}")
                            if ltp >= tsl:
                                print("❌ TSL hit (SHORT) — Exiting")
                                exit_position()
                                continue

                # ======= Histogram flip every 30-min boundary =======
                if is_30min_boundary():
                    print(f"📊 Histogram flip check @ {now.strftime('%H:%M:%S')}")
                    result, status = fetch_histogram(sym)
                    if status != "ok" or result is None:
                        print("⚠️ Histogram fetch failed, skipping this cycle.")
                    else:
                        if side == "LONG" and result["cross_to_red"]:
                            print("📉 MACD flip to RED — Exiting LONG")
                            exit_position()
                        elif side == "SHORT" and result["cross_to_green"]:
                            print("📈 MACD flip to GREEN — Exiting SHORT")
                            exit_position()

        except Exception as e:
            print("❌ Monitor error:", e)

        time.sleep(60)

def start_monitor():
    threading.Thread(target=monitor_loop, daemon=True).start()
