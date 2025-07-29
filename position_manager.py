from config import kite, current_position, SL_PERCENT, TSL_PERCENT
import time
import threading

monitor_thread_started = False  # Prevent duplicate threads

def fetch_existing_position():
    global monitor_thread_started
    positions = kite.positions()
    for pos in positions['net']:
        if pos['tradingsymbol'].startswith("SBIN") and pos['product'] == "NRML":
            avg_price = pos['average_price']
            symbol = pos['tradingsymbol']
            ltp = kite.ltp(f"NFO:{symbol}")[f"NFO:{symbol}"]['last_price']
            side = "LONG" if pos['quantity'] > 0 else "SHORT"

            stop_loss = avg_price * (1 - SL_PERCENT) if side == "LONG" else avg_price * (1 + SL_PERCENT)
            trailing_sl = ltp * (1 - TSL_PERCENT) if side == "LONG" else ltp * (1 + TSL_PERCENT)

            current_position.update({
                "active": True,
                "symbol": symbol,
                "side": side,
                "entry_price": avg_price,
                "stop_loss": stop_loss,
                "trailing_sl": trailing_sl,
                "quantity": pos['quantity']
            })

            print(f"📌 Resumed monitoring existing position: {current_position}")

            if not monitor_thread_started:
                threading.Thread(target=log_position_pnl, daemon=True).start()
                monitor_thread_started = True

            return True
    return False

def log_position_pnl():
    while current_position["active"]:
        try:
            symbol = current_position["symbol"]
            ltp = kite.ltp(f"NFO:{symbol}")[f"NFO:{symbol}"]['last_price']
            entry = current_position["entry_price"]
            qty = current_position["quantity"] or 0
            side = current_position["side"]

            # TSL Update
            tsl_updated = False
            if side == "LONG" and ltp > entry:
                new_tsl = ltp * (1 - TSL_PERCENT)
                if new_tsl > current_position["trailing_sl"]:
                    current_position["trailing_sl"] = new_tsl
                    tsl_updated = True
            elif side == "SHORT" and ltp < entry:
                new_tsl = ltp * (1 + TSL_PERCENT)
                if new_tsl < current_position["trailing_sl"]:
                    current_position["trailing_sl"] = new_tsl
                    tsl_updated = True

            pnl = (ltp - entry) * qty if side == "LONG" else (entry - ltp) * qty
            sl_or_tsl = current_position["stop_loss"] if ltp <= entry else current_position["trailing_sl"]
            sl_type = "SL" if ltp <= entry else "TSL"

            # Align to nearest 5-min boundary
            now = time.localtime()
            aligned_minute = now.tm_min - (now.tm_min % 5)
            timestamp = f"{now.tm_hour:02d}:{aligned_minute:02d}:00"

            print(f"\n📈 Monitoring Update @ {timestamp}")
            print(f"Symbol: {symbol}")
            print(f"Side: {side}")
            print(f"Entry: {entry:.2f}")
            print(f"Current Price: {ltp:.2f}")
            print(f"PnL: {pnl:.2f}")
            print(f"Using: {sl_type} @ {sl_or_tsl:.2f}")
            if tsl_updated:
                print(f"🔁 TSL updated to: {current_position['trailing_sl']:.2f}")
            print(flush=True)

        except Exception as e:
            print("⚠️ Error during PnL log:", str(e), flush=True)

        time.sleep(300)  # Sleep 5 minutes
