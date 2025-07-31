import time
import logging
import datetime
import threading
import sys
import os
import traceback

from config import kite, DB_FILE_NAME, DB_LOCK_FILE, monitor_frequency, shutdown_requested, current_position, TSL_TRAIL_AMOUNT
# The `position_manager` module has been refactored. The correct function to import is `fetch_existing_position`, not `get_latest_position`.
from position_manager import fetch_existing_position, update_position, save_position
from symbol_resolver import resolve_token
from order_manager import exit_position, place_order
from gcs_sync import upload_file_to_gcs

# Configure logging for this module
logger = logging.getLogger(__name__)

# --- Helper functions for monitoring logic ---

def is_market_open():
    """
    Checks if the current time is within market hours (9:15 AM to 3:30 PM IST) for NSE.
    Returns True if open, False otherwise.
    """
    # Assuming IST for simplicity. Timezone handling can be more complex if needed.
    current_time = datetime.datetime.now().time()
    market_open = datetime.time(9, 15)
    market_close = datetime.time(15, 30)
    return market_open <= current_time <= market_close

def is_position_active():
    """
    Returns True if a valid position is considered active, False otherwise.
    A position is active if the 'active' flag is True and the entry price is non-zero
    and the quantity is non-zero.
    This prevents the bot from getting stuck monitoring a phantom position.
    """
    return (current_position.get("active", False) and 
            current_position.get("entry_price", 0) > 0 and
            current_position.get("quantity", 0) > 0)

def calculate_tsl(ltp, side, entry_price, initial_sl):
    """
    Calculates the new Trailing Stop Loss (TSL) based on the latest LTP.
    Returns the updated TSL.
    """
    try:
        if side == "LONG":
            profit = ltp - entry_price
            new_tsl = max(initial_sl, entry_price + (profit - TSL_TRAIL_AMOUNT))
            return new_tsl if new_tsl < ltp else initial_sl
        
        elif side == "SHORT":
            profit = entry_price - ltp
            new_tsl = min(initial_sl, entry_price - (profit - TSL_TRAIL_AMOUNT))
            return new_tsl if new_tsl > ltp else initial_sl
        
    except Exception as e:
        logger.error(f"Error calculating TSL: {e}\n{traceback.format_exc()}")
        return initial_sl

# --- Main monitoring loop function ---

def monitor_loop():
    """
    The main monitoring thread function.
    It runs continuously in the background, checking for SL/TSL hits and updating position info.
    """
    global current_position

    while not shutdown_requested.is_set():
        # Check if the market is open before performing any actions
        if not is_market_open():
            logger.info("Market is closed. Waiting for market to open...")
            time.sleep(300) # Sleep for 5 minutes when market is closed
            continue

        # Check if a lock file exists, indicating another process is modifying the DB
        if os.path.exists(DB_LOCK_FILE):
            logger.debug("Database is locked. Skipping this monitor iteration.")
            time.sleep(monitor_frequency)
            continue
        
        try:
            # Re-read position from DB in case it was updated by the webhook
            # The function name has been corrected to `fetch_existing_position`.
            db_position = fetch_existing_position()
            if db_position:
                current_position.update(db_position)
            
            # If no active position, just wait for a new trade signal
            if not is_position_active():
                logger.info("No active position. Waiting for a trade to be placed...")
                time.sleep(monitor_frequency)
                continue

            # --- Active Position Monitoring Logic ---
            symbol = current_position["symbol"]
            side = current_position["side"]
            entry_price = current_position["entry_price"]
            effective_sl = current_position.get("effective_sl")

            # Fetch latest price
            try:
                # Use resolve_token to get the token for the trading symbol
                instrument_token = resolve_token(symbol)
                if not instrument_token:
                    logger.error(f"Could not resolve instrument token for {symbol}. Cannot fetch LTP.")
                    time.sleep(monitor_frequency)
                    continue

                ltp_data = kite.ltp([f"NFO:{symbol}"])
                ltp = ltp_data[f"NFO:{symbol}"]["last_price"]
            except Exception as e:
                logger.error(f"Failed to fetch LTP for {symbol}: {e}")
                time.sleep(monitor_frequency)
                continue

            # Calculate PnL and TSL
            pnl = (ltp - entry_price) * current_position["quantity"] if side == "LONG" else (entry_price - ltp) * current_position["quantity"]
            
            if effective_sl is None:
                # If effective_sl is not set, this is the first monitor tick, use initial_sl
                effective_sl = current_position.get("initial_sl")
            
            # Now, calculate the TSL based on the latest price and current effective SL
            new_effective_sl = calculate_tsl(ltp, side, entry_price, effective_sl)
            
            # Only update the position if the TSL has actually moved
            if new_effective_sl != effective_sl:
                current_position["effective_sl"] = new_effective_sl
                save_position(current_position)
                upload_file_to_gcs() # Sync to GCS after every update
            
            # Log a summary of the current position
            logger.info("\n--- Monitoring Update @ %s ---", datetime.datetime.now().strftime("%H:%M:%S"))
            logger.info("Symbol: %s | Side: %s | Entry: %.2f", symbol, side, entry_price)
            logger.info("Current Price: %.2f | PnL: %.2f", ltp, pnl)
            logger.info("Initial SL: %.2f | Effective SL: %.2f", current_position.get("initial_sl"), new_effective_sl)
            
            # --- Check for Exit Conditions ---
            
            # Check for SL/TSL hit
            if (side == "LONG" and ltp <= new_effective_sl) or \
               (side == "SHORT" and ltp >= new_effective_sl):
                logger.warning("❌ SL/TSL hit (%s) — Exiting at %.2f (Effective SL: %.2f)", side, ltp, new_effective_sl)
                # Call exit_position only if there is a quantity to exit
                if current_position.get("quantity", 0) > 0:
                    exit_position() # This function will reset current_position to inactive
                else:
                    logger.warning("Position has zero quantity. Resetting state without placing an order.")
                    # Manually reset the position if it's a phantom one
                    current_position.update({
                        "active": False,
                        "quantity": 0,
                        "entry_price": 0.0,
                    })
                    save_position(current_position)
                    upload_file_to_gcs()
                    
        except Exception as e:
            logger.critical("Unhandled error in monitor_loop: %s", e, exc_info=True)
            # Ensure the position is reset in case of an unhandled error
            current_position.update({
                "active": False,
                "quantity": 0,
                "entry_price": 0.0,
            })
            save_position(current_position)
            upload_file_to_gcs()
        
        finally:
            time.sleep(monitor_frequency)

    logger.info("Monitor loop stopped gracefully.")
