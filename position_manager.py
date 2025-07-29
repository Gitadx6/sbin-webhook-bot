from config import kite, current_position, SL_PERCENT, TSL_PERCENT
import time
import threading


def fetch_existing_position():
    positions = kite.positions()
    for pos in positions['net']:
        if pos['tradingsymbol'].startswith("SBIN") and pos['product'] == "NRML":
            avg_price = pos['average_price']
            ltp = kite.ltp(f"NFO:{pos['tradingsymbol']}")[f"NFO:{pos['tradingsymbol']}"]['last_price']
            side = "LONG" if pos['quantity'] > 0 else "SHORT"

            if side == "LONG":
                stop_loss = avg_price * (1 - SL_PERCENT)
                trailing_sl = avg_price * (1 - TSL_PERCENT)
            else:
                stop_loss = avg_price * (1 + SL_PERCENT)
                trailing_sl = avg_price * (1 + TSL_PERCENT)

            current_position.update({
                "active": True,
                "symbol": pos['tradingsymbol'],
                "side": side,
                "entry_price": avg_price,
                "stop_loss": stop_loss,
                "trailing_sl": trailing_sl,
                "quantity": pos['quantity']
            })

            print(f"📌 Resumed monitoring existing position: {current_position}")

            # Start PnL logging thread
            threading.Thread(target=log_position_pnl, daemon=True).start()
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

            pnl = (ltp - entry) * qty if side == "LONG" else (entry - ltp) * qty
            sl_or_tsl = current_position["stop_loss"] if ltp <= entry else current_position["trailing_sl"]
            sl_type = "SL" if ltp <= entry else "TSL"

            print(f"\n📈 Monitoring Update @ {time.strftime('%H:%M:%S')}\nSymbol: {symbol}\nSide: {side}\nEntry: {entry:.2f}\nCurrent Price: {ltp:.2f}\nPnL: {pnl:.2f}\nUsing: {sl_type} @ {sl_or_tsl:.2f}\n", flush=True)

        except Exception as e:
            print("⚠️ Error during PnL log:", str(e), flush=True)

        time.sleep(300)  # Log every 5 minutes
