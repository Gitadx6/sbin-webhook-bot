from config import kite, current_position

def place_order(symbol, direction, price):
    action = "BUY" if direction == "LONG" else "SELL"
    quantity = 1
    order_id = kite.place_order(
        tradingsymbol=symbol,
        exchange="NFO",
        transaction_type=action,
        quantity=quantity,
        order_type="MARKET",
        product="NRML",
        variety="regular"
    )
    sl = price * (0.995 if direction == "LONG" else 1.005)
    tsl = sl

    current_position.update({
        "symbol": symbol,
        "side": direction,
        "entry_price": price,
        "quantity": quantity,
        "stop_loss": sl,
        "trailing_sl": tsl,
        "active": True
    })
    return order_id

def exit_position():
    if not current_position["active"]:
        return

    action = "SELL" if current_position["side"] == "LONG" else "BUY"
    kite.place_order(
        tradingsymbol=current_position["symbol"],
        exchange="NFO",
        transaction_type=action,
        quantity=current_position["quantity"],
        order_type="MARKET",
        product="NRML",
        variety="regular"
    )
    current_position["active"] = False
