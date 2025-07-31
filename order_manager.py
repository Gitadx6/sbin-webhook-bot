import logging
import traceback

from config import kite, current_position, TRADE_QUANTITY
from position_manager import save_position
from gcs_sync import upload_file_to_gcs

logger = logging.getLogger(__name__)

def place_order(signal_type):
    """
    Places a new market order based on the signal type.
    Updates the global position state upon a successful order.
    Returns the order ID on success, None on failure.
    """
    if not kite:
        logger.error("KiteConnect is not initialized. Cannot place order.")
        return None
    
    # Check if a position is already active to prevent double-entry
    if current_position.get("active", False):
        logger.warning("Attempted to place a new order while a position is active. Aborting.")
        return None

    # Determine order parameters
    if signal_type == "LONG":
        transaction_type = "BUY"
    elif signal_type == "SHORT":
        transaction_type = "SELL"
    else:
        logger.error(f"Invalid signal_type for order placement: {signal_type}")
        return None

    try:
        # Resolve the instrument token
        instrument_token = kite.instruments("NFO", [current_position["symbol"]])[0]['instrument_token']

        # Place the order
        order = kite.place_order(
            variety="regular",
            exchange="NFO",
            tradingsymbol=current_position["symbol"],
            transaction_type=transaction_type,
            quantity=TRADE_QUANTITY,
            product="NRML",
            order_type="MARKET",
            validity="DAY"
        )
        logger.info(f"✅ Order placed successfully! Order ID: {order['order_id']}")

        # Update the global position state
        current_position.update({
            "active": True,
            "side": signal_type,
            "quantity": TRADE_QUANTITY,
            "order_id": order["order_id"],
            # Entry price and SL will be updated by the monitor loop after the order is filled
            "entry_price": 0.0,
            "initial_sl": 0.0,
        })
        save_position(current_position)
        upload_file_to_gcs()
        
        return order["order_id"]

    except Exception as e:
        logger.error(f"Failed to place order for {current_position['symbol']}: {e}\n{traceback.format_exc()}")
        return None

def exit_position():
    """
    Exits the currently active position by placing a market order with the opposite transaction type.
    Resets the global position state upon a successful exit.
    """
    if not kite:
        logger.error("KiteConnect not initialized. Cannot exit position.")
        return

    # Check if there is an active position with a non-zero quantity to exit
    if not current_position.get("active", False) or current_position.get("quantity", 0) == 0:
        logger.warning("No active position or zero quantity to exit. Aborting exit.")
        # Ensure state is reset even if there was a phantom position
        reset_position_state()
        return

    # Determine the transaction type to exit the position
    if current_position["side"] == "LONG":
        transaction_type = "SELL"
    elif current_position["side"] == "SHORT":
        transaction_type = "BUY"
    else:
        logger.error("Cannot exit position. Invalid 'side' found in current_position.")
        reset_position_state()
        return

    try:
        # Place the exit order
        order = kite.place_order(
            variety="regular",
            exchange="NFO",
            tradingsymbol=current_position["symbol"],
            transaction_type=transaction_type,
            quantity=current_position["quantity"],
            product="NRML",
            order_type="MARKET",
            validity="DAY"
        )
        logger.info(f"✅ Exit order placed successfully for {current_position['symbol']}. Order ID: {order['order_id']}")

    except Exception as e:
        logger.error(f"Failed to place exit order for {current_position['symbol']}: {e}\n{traceback.format_exc()}")
    
    finally:
        # Always reset the position state, whether the order succeeded or failed,
        # to prevent the monitor from getting stuck in an infinite loop.
        reset_position_state()

def reset_position_state():
    """
    Resets the global current_position to its default, inactive state.
    Also saves this state to the database and syncs to GCS.
    """
    current_position.update({
        "symbol": "",
        "token": None,
        "side": "NONE",
        "active": False,
        "quantity": 0,
        "entry_price": 0.0,
        "initial_sl": 0.0,
        "effective_sl": None,
    })
    save_position(current_position)
    upload_file_to_gcs()
    logger.info("Global position state has been reset.")
