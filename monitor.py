```python
import time
import threading
import datetime
import logging
import traceback # For detailed error tracing

# Configure logging
logging.basicConfig(
    level=logging.INFO, # Set to logging.DEBUG for more verbose output during development
    format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s',
    handlers=[
        logging.StreamHandler(), # Output logs to console
        # logging.FileHandler("monitor_bot.log") # Uncomment to also log to a file
    ]
)
logger = logging.getLogger(__name__)

# Assuming these imports are correctly set up and available
from config import current_position, kite, SL_PERCENT, TSL_PERCENT
from order_manager import exit_position
from histogram import fetch_histogram
from price_tracker import load_price_track, save_price_track, init_db
from gdrive_sync import upload_file # For Drive upload

# --- Global variables for controlled time checks ---
_last_30min_check_timestamp = None
_last_5min_check_timestamp = None

def is_30min_boundary_once():
    """
    Checks if it's a 30-minute boundary (e.g., HH:00:XX, HH:30:XX)
    and ensures the check is performed only once per 30-minute block.
    """
    global _last_30min_check_timestamp
    now = datetime.datetime.now()
    # Check if it's the 30-minute mark and within the first 10 seconds
    if now.minute % 30 == 0 and now.second < 10:
        # Create a timestamp representing the start of the current 30-minute block
        current_30min_block = now.replace(minute=(now.minute // 30) * 30, second=0, microsecond=0)
        if _last_30min_check_timestamp != current_30min_block:
            _last_30min_check_timestamp = current_30min_block
            return True
    return False

def is_5min_boundary_once():
    """
    Checks if it's a 5-minute boundary (e.g., HH:00:XX, HH:05:XX, etc.)
    and ensures the check is performed only once per 5-minute block.
    """
    global _last_5min_check_timestamp
    now = datetime.datetime.now()
    # Check if it's a 5-minute mark and within the first 10 seconds
    if now.minute % 5 == 0 and now.second < 10:
        # Create a timestamp representing the start of the current 5-minute block
        current_5min_block = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0)
        if _last_5min_check_timestamp != current_5min_block:
            _last_5min_check_timestamp = current_5min_block
            return True
    return False

def format_pnl(pnl):
    """Formats PnL for colored console output."""
    if pnl < 0:
        return f"\033[91m{pnl:.2f}\033[0m"  # Red for negative
    else:
        return f"\033[92m{pnl:.2f}\033[0m"  # Green for positive

def monitor_loop():
    """
    Main monitoring loop for active trading positions.
    Manages SL, TSL, and histogram-based exits.
    """
    init_db()  # Initialize SQLite DB for price tracking
    last_monitor_minute = -1 # Tracks when last monitoring update was printed

    logger.info("Monitor loop started.")

    while True:
        try:
            now = datetime.datetime.now()
            minute = now.minute

            # Check if current_position is active. If not, pause and continue.
            # Using .get() for safer access in case 'active' key is missing.
            if not current_position.get("active", False):
                if last_monitor_minute != -1: # Only log once when position becomes inactive
                    logger.info("No active position. Waiting...")
                    last_monitor_minute = -1 # Reset to ensure message prints again when position becomes active
                time.sleep(10) # Sleep for a longer duration when idle to save resources
                continue # Skip the rest of the loop if no active position

            sym = current_position["symbol"]
            side = current_position["side"]
            entry = current_position["entry_price"]
            initial_stop_loss = current_position["stop_loss"] # The original SL set when trade was placed
            quantity = current_position.get("quantity", 750) # Default quantity

            # Fetch Last Traded Price (LTP)
            try:
                ltp_data = kite.ltp(f"NFO:{sym}")
                ltp = ltp_data[f"NFO:{sym}"]["last_price"]
            except KeyError:
                logger.error(f"Could not fetch LTP for {sym}. Data structure unexpected: {ltp_data}")
                time.sleep(5) # Shorter sleep to retry fetching LTP soon
                continue
            except Exception as e:
                logger.error(f"Error fetching LTP for {sym}: {e}")
                time.sleep(5) # Shorter sleep to retry fetching LTP soon
                continue

            # --- PnL Calculation ---
            pnl = (ltp - entry) * quantity if side == "LONG" else (entry - ltp) * quantity

            if minute != last_monitor_minute:
                last_monitor_minute = minute
                effective_sl_display = current_position.get("effective_stop_loss", initial_stop_loss)
                logger.info(f"\n--- Monitoring Update @ {now.strftime('%H:%M:%S')} ---")
                logger.info(f"Symbol: {sym} | Side: {side} | Entry: {entry:.2f}")
                logger.info(f"Current Price: {ltp:.2f} | PnL: {format_pnl(pnl)}")
                logger.info(f"Initial SL: {initial_stop_loss:.2f} | Effective SL: {effective_sl_display:.2f}")

            # ===== SL and TSL checks every 5 minutes =====
            if is_5min_boundary_once():
                logger.info(f"\n🛡️ SL/TSL Check @ {now.strftime('%H:%M:%S')} | Price: {ltp:.2f}")

                # Load previous TSL tracking (highest/lowest price seen)
                # This is crucial for persistence across restarts
                track = load_price_track()
                
                # Initialize highest/lowest prices if not already set (e.g., first run after trade open)
                if track.get("highest_price") is None:
                    track["highest_price"] = entry
                if track.get("lowest_price") is None:
                    track["lowest_price"] = entry

                # Get the current effective stop loss, initialized with initial SL if not set
                effective_stop_loss = current_position.get("effective_stop_loss", initial_stop_loss)

                if side == "LONG":
                    # Always update highest price to track market's favorability
                    high = max(track["highest_price"], ltp)
                    save_price_track(high=high) # Save the new high locally
                    upload_file() # Upload the updated price track file to Google Drive

                    # Calculate potential TSL based on the new high
                    potential_tsl = high * (1 - TSL_PERCENT)

                    # The effective stop loss for a LONG position is the higher of:
                    # 1. The initial fixed stop loss.
                    # 2. The calculated trailing stop loss (but not higher than current LTP,
                    #    to avoid immediate false hits if TSL_PERCENT is too aggressive).
                    effective_stop_loss = max(initial_stop_loss, min(potential_tsl, ltp))

                    # Update the effective_stop_loss in current_position for next iteration and display
                    current_position["effective_stop_loss"] = effective_stop_loss
                    logger.info(f"🔼 LONG - Initial SL: {initial_stop_loss:.2f} | Trailed TSL (potential): {potential_tsl:.2f} | High: {high:.2f} | Effective SL: {effective_stop_loss:.2f}")

                    # Check if effective SL is hit
                    if ltp <= effective_stop_loss:
                        logger.warning(f"❌ SL/TSL hit (LONG) — Exiting at {ltp:.2f} (Effective SL: {effective_stop_loss:.2f})")
                        exit_position()
                        # Exit position should set current_position["active"] = False
                        # The next loop iteration will then handle the inactive state.
                        continue # Go to next loop iteration to re-evaluate position status

                elif side == "SHORT":
                    # Always update lowest price to track market's favorability
                    low = min(track["lowest_price"], ltp)
                    save_price_track(low=low) # Save the new low locally
                    upload_file() # Upload the updated price track file to Google Drive

                    # Calculate potential TSL based on the new low
                    potential_tsl = low * (1 + TSL_PERCENT)

                    # The effective stop loss for a SHORT position is the lower of:
                    # 1. The initial fixed stop loss.
                    # 2. The calculated trailing stop loss (but not lower than current LTP,
                    #    to avoid immediate false hits if TSL_PERCENT is too aggressive).
                    effective_stop_loss = min(initial_stop_loss, max(potential_tsl, ltp))

                    # Update the effective_stop_loss in current_position for next iteration and display
                    current_position["effective_stop_loss"] = effective_stop_loss
                    logger.info(f"🔽 SHORT - Initial SL: {initial_stop_loss:.2f} | Trailed TSL (potential): {potential_tsl:.2f} | Low: {low:.2f} | Effective SL: {effective_stop_loss:.2f}")

                    # Check if effective SL is hit
                    if ltp >= effective_stop_loss:
                        logger.warning(f"❌ SL/TSL hit (SHORT) — Exiting at {ltp:.2f} (Effective SL: {effective_stop_loss:.2f})")
                        exit_position()
                        # Exit position should set current_position["active"] = False
                        # The next loop iteration will then handle the inactive state.
                        continue # Go to next loop iteration to re-evaluate position status

            # ===== Histogram flip check every 30-min boundary =====
            if is_30min_boundary_once():
                logger.info(f"\n📊 Histogram flip check @ {now.strftime('%H:%M:%S')}")
                result, status = fetch_histogram(sym)
                if status != "ok" or result is None:
                    logger.warning("⚠️ Histogram fetch failed, skipping this cycle.")
                else:
                    if side == "LONG" and result.get("cross_to_red"):
                        logger.warning("📉 MACD flip to RED — Exiting LONG due to histogram flip.")
                        exit_position()
                    elif side == "SHORT" and result.get("cross_to_green"):
                        logger.warning("📈 MACD flip to GREEN — Exiting SHORT due to histogram flip.")
                        exit_position()

        except Exception as e:
            logger.critical(f"Unhandled error in monitor_loop: {e}\n{traceback.format_exc()}")
            # Consider adding a longer sleep or a mechanism to restart if critical errors occur
            # For now, it will just log and continue after the sleep.

        time.sleep(1) # Sleep for 1 second to make the loop more responsive for LTP and time checks

def start_monitor():
    """
    Starts the monitor_loop in a separate daemon thread.
    Initializes global time check variables.
    """
    global _last_30min_check_timestamp, _last_5min_check_timestamp
    _last_30min_check_timestamp = None
    _last_5min_check_timestamp = None
    
    logger.info("Starting monitor thread...")
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True, name="MonitorThread")
    monitor_thread.start()
    logger.info("Monitor thread started in background.")

# Example of how you might call start_monitor in your main application flow:
if __name__ == "__main__":
    # This is a placeholder for how your main script would use this.
    # In a real trading bot, you'd likely have:
    # 1. Kite login/session setup
    # 2. Initial position fetching or placement
    # 3. Then start the monitor.

    logger.info("Simulating main application startup...")

    # --- Dummy Config and Kite objects for standalone testing ---
    # In your actual environment, these would be populated by your 'config.py'
    # and successful Kite login.
    class MockKite:
        def ltp(self, instrument):
            # Simulate price movement for testing
            if instrument == "NFO:BANKNIFTY24AUG47000CE":
                # For testing a LONG position
                # You can change this to simulate price going up/down
                # Current time: Thursday, July 31, 2025 at 12:45:38 PM IST.
                # Let's simulate some price action around 200 entry
                mock_price = 200 + (time.time() % 30) - 15 # Price between 185 and 215
                if time.time() % 60 < 10: # Simulate a dip every minute start
                    mock_price -= 20 # Simulate hitting SL/TSL
                return {instrument: {"last_price": mock_price}}
            elif instrument == "NFO:NIFTY24AUG22000PE":
                # For testing a SHORT position
                mock_price = 100 - (time.time() % 30) + 15 # Price between 85 and 115
                if time.time() % 60 < 10: # Simulate a rise every minute start
                    mock_price += 20 # Simulate hitting SL/TSL
                return {instrument: {"last_price": mock_price}}
            return {instrument: {"last_price": 100}} # Default fallback


    class MockOrderManager:
        def exit_position(self):
            logger.info("🚨 Mock: Position exit triggered!")
            current_position["active"] = False
            current_position["symbol"] = None # Clear symbol

    class MockHistogram:
        def fetch_histogram(self, symbol):
            # Simulate a histogram flip every ~30 mins (for testing)
            current_minute = datetime.datetime.now().minute
            cross_to_red = (current_minute % 30 == 0 and current_minute % 60 != 0 and datetime.datetime.now().second < 15)
            cross_to_green = (current_minute % 30 == 0 and current_minute % 60 == 0 and datetime.datetime.now().second < 15)
            return {"cross_to_red": cross_to_red, "cross_to_green": cross_to_green}, "ok"

    class MockPriceTracker:
        _track_data = {"highest_price": None, "lowest_price": None}
        def init_db(self):
            logger.info("Mock DB initialized.")
        def load_price_track(self):
            return self._track_data
        def save_price_track(self, high=None, low=None):
            if high is not None:
                self._track_data["highest_price"] = high
            if low is not None:
                self._track_data["lowest_price"] = low
            logger.debug(f"MockPriceTracker: Saved track data: {self._track_data}")

    class MockGdriveSync:
        def upload_file(self):
            logger.debug("Mock: Uploading file to Google Drive...")

    # Assign mocks to variables used in the main code
    kite = MockKite()
    exit_position = MockOrderManager().exit_position
    fetch_histogram = MockHistogram().fetch_histogram
    load_price_track = MockPriceTracker().load_price_track
    save_price_track = MockPriceTracker().save_price_track
    init_db = MockPriceTracker().init_db
    upload_file = MockGdriveSync().upload_file

    # --- Define current_position (this would normally come from your order placement) ---
    current_position = {
        "active": True,
        "symbol": "BANKNIFTY24AUG47000CE", # Change to "NIFTY24AUG22000PE" to test SHORT
        "side": "LONG", # Change to "SHORT" to test SHORT
        "entry_price": 200.0, # Adjust for testing
        "stop_loss": 180.0,  # Initial fixed stop loss
        "quantity": 750,
        "effective_stop_loss": 180.0 # Crucial: Initialize effective_stop_loss
    }
    # These are constants, assumed to be in config.py
    SL_PERCENT = 0.10  # 10%
    TSL_PERCENT = 0.005 # 0.5% for trailing (or whatever your actual value is)


    start_monitor()

    # Keep the main thread alive so the daemon monitor_loop continues to run
    try:
        while True:
            time.sleep(1)
            # You could add other main thread activities here if needed
    except KeyboardInterrupt:
        logger.info("Main application interrupted. Shutting down.")
    except Exception as e:
        logger.critical(f"Main application error: {e}\n{traceback.format_exc()}")
