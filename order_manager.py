from config import kite, current_position, SL_PERCENT, TSL_PERCENT

FUTURE_LOT_SIZE = 750  # Set SBIN lot size here

def place_order(symbol, direction, price):
    action = "BUY" if direction == "LONG" else "SELL"
    quantity = FUTURE_LOT_SIZE

    order_id = kite.place_order(
        tradingsymbol=symbol,
        exchange="NFO",
        transaction_type=action,
        quantity=quantity,
        order_type="MARKET",
        product="NRML",
        variety="regular"
    )

    sl = price * (1 - SL_PERCENT) if direction == "LONG" else price * (1 + SL_PERCENT)
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

    print(f"✅ Order placed: {direction} {quantity} of {symbol} at {price}")
    print(f"🛡️ SL set at {sl:.2f}, TSL initialized at {tsl:.2f}")
    return order_id


def exit_position():
    if not current_position["active"]:
        print("⚠️ No active position to exit.")
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

    print(f"🔁 Exited position: {current_position['side']} {current_position['quantity']} of {current_position['symbol']}")
    current_position["active"] = False
