from config import kite, current_position
def fetch_existing_position():
    positions = kite.positions()
    for pos in positions['net']:
        if pos['tradingsymbol'].startswith("SBIN") and pos['product'] == "NRML":
            avg_price = pos['average_price']
            ltp = kite.ltp(f"NFO:{pos['tradingsymbol']}")[f"NFO:{pos['tradingsymbol']}"]['last_price']
            side = "LONG" if pos['quantity'] > 0 else "SHORT"
            stop_loss = avg_price * (0.9925 if side == "LONG" else 1.0075)
            trailing_sl = stop_loss

            current_position.update({
                "active": True,
                "symbol": pos['tradingsymbol'],
                "side": side,
                "entry_price": avg_price,
                "stop_loss": stop_loss,
                "trailing_sl": trailing_sl
            })
            print(f"📌 Resumed monitoring existing position: {current_position}")
            return True
    return False

def fetch_existing_position():
    positions = kite.positions()
    for pos in positions['net']:
        if pos['tradingsymbol'].startswith("SBIN") and pos['product'] == "NRML":
            avg_price = pos['average_price']
            ltp = kite.ltp(f"NFO:{pos['tradingsymbol']}")[f"NFO:{pos['tradingsymbol']}"]['last_price']
            side = "LONG" if pos['quantity'] > 0 else "SHORT"
            stop_loss = avg_price * (0.9925 if side == "LONG" else 1.0075)
            trailing_sl = stop_loss

            current_position.update({
                "active": True,
                "symbol": pos['tradingsymbol'],
                "side": side,
                "entry_price": avg_price,
                "stop_loss": stop_loss,
                "trailing_sl": trailing_sl
            })
            print(f"📌 Resumed monitoring existing position: {current_position}")
            return True
    return False
