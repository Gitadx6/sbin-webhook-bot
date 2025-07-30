import time
import threading
from config import current_position, kite, SL_PERCENT, TSL_PERCENT
from order_manager import exit_position
from histogram import fetch_histogram
from price_tracker import load_price_track, save_price_track

def monitor_loop():
    while True:
        try:
            if current_position["active"]:
                sym = current_position["symbol"]
                ltp = kite.ltp(f"NFO:{sym}")[f"NFO:{sym}"]["last_price"]

                # SL check
                if current_position["side"] == "LONG" and ltp <= current_position["stop_loss"]:
                    exit_position()
                    continue
                elif current_position["side"] == "SHORT" and ltp >= current_position["stop_loss"]:
                    exit_position()
                    continue

                # Load highest/lowest from disk
                track = load_price_track()

                # Initialize high/low if missing
                if track.get("highest_price") is None:
                    track["highest_price"] = current_position["entry_price"]
                if track.get("lowest_price") is None:
                    track["lowest_price"] = current_position["entry_price"]

                # TSL check and update
                if current_position["side"] == "LONG":
                    high = track["highest_price"]
                    if ltp > high:
                        high = ltp
                        save_price_track(high=high)
                    tsl = high * (1 - TSL_PERCENT)
                    current_position["trailing_sl"] = tsl
                    if ltp <= tsl:
                        exit_position()
                        continue

                elif current_position["side"] == "SHORT":
                    low = track["lowest_price"]
                    if ltp < low:
                        low = ltp
                        save_price_track(low=low)
                    tsl = low * (1 + TSL_PERCENT)
                    current_position["trailing_sl"] = tsl
                    if ltp >= tsl:
                        exit_position()
                        continue

                # Histogram flip exit — safe unpack
                result = fetch_histogram(sym)
                if result and len(result) == 4:
                    _, _, hist, prev_hist = result
                    if current_position["side"] == "LONG" and hist < 0 and prev_hist >= 0:
                        exit_position()
                    elif current_position["side"] == "SHORT" and hist > 0 and prev_hist <= 0:
                        exit_position()
                else:
                    print(f"⚠️ Skipping histogram check for {sym}: Incomplete histogram data")

        except Exception as e:
            print("❌ Monitor error:", e)

        time.sleep(60)

def start_monitor():
    threading.Thread(target=monitor_loop, daemon=True).start()
