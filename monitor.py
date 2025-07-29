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
                elif current_position["side"] == "SHORT" and ltp >= current_position["stop_loss"]:
                    exit_position()

                # Load highest/lowest from disk
                track = load_price_track()

                # TSL check and update
                if current_position["side"] == "LONG":
                    high = track.get("highest_price", current_position["entry_price"])
                    if ltp > high:
                        high = ltp
                        save_price_track(high=high)
                    tsl = high * (1 - TSL_PERCENT)
                    current_position["trailing_sl"] = tsl
                    if ltp <= tsl:
                        exit_position()

                elif current_position["side"] == "SHORT":
                    low = track.get("lowest_price", current_position["entry_price"])
                    if ltp < low:
                        low = ltp
                        save_price_track(low=low)
                    tsl = low * (1 + TSL_PERCENT)
                    current_position["trailing_sl"] = tsl
                    if ltp >= tsl:
                        exit_position()

                # Histogram flip exit
                _, _, hist, prev_hist = fetch_histogram(sym)
                if current_position["side"] == "LONG" and hist < 0 and prev_hist >= 0:
                    exit_position()
                elif current_position["side"] == "SHORT" and hist > 0 and prev_hist <= 0:
                    exit_position()

        except Exception as e:
            print("❌ Monitor error:", e)

        time.sleep(60)

def start_monitor():
    threading.Thread(target=monitor_loop, daemon=True).start()
