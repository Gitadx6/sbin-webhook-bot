import time
from config import current_position, kite
from order_manager import exit_position
from histogram import fetch_histogram
import threading

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

                # TSL check + update
                if current_position["side"] == "LONG":
                    if ltp > current_position["entry_price"]:
                        tsl = ltp * 0.995
                        if tsl > current_position["trailing_sl"]:
                            current_position["trailing_sl"] = tsl
                    if ltp <= current_position["trailing_sl"]:
                        exit_position()

                elif current_position["side"] == "SHORT":
                    if ltp < current_position["entry_price"]:
                        tsl = ltp * 1.005
                        if tsl < current_position["trailing_sl"]:
                            current_position["trailing_sl"] = tsl
                    if ltp >= current_position["trailing_sl"]:
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
