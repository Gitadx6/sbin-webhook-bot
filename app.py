import logging
import threading
import sys
import os
import signal

from flask import Flask, jsonify, request
from config import kite, current_position, shutdown_requested
from monitor import monitor_loop
from symbol_resolver import resolve_sbin_future
from macd_indicator import is_bullish_crossover
from order_manager import place_order

# --- Logging Setup ---
# Configure logging for the entire application
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Bot Initialization and Shutdown Logic ---

def initialize_bot():
    """
    Initializes the bot by resolving the trading symbol and starting the monitor thread.
    """
    logger.info("Starting bot initialization...")
    
    # 1. Resolve the trading symbol for the current month's contract
    try:
        # Resolve the SBIN future symbol and store it globally
        trading_symbol = resolve_sbin_future()
        current_position["symbol"] = trading_symbol
        logger.info(f"Successfully resolved trading symbol: {trading_symbol}")
    except Exception as e:
        logger.critical(f"Bot failed to initialize: {e}")
        # If symbol resolution fails, we cannot proceed.
        # This will cause the app to exit.
        return False
    
    # 2. Check for an existing position from the database
    # fetch_existing_position()
    # TODO: We'll implement this function later to resume a trade if it was running
    
    # 3. Start the monitor loop in a separate thread
    monitor_thread = threading.Thread(target=monitor_loop, name="MonitorThread")
    monitor_thread.daemon = True # Allows the main program to exit even if this thread is running
    monitor_thread.start()
    logger.info("Monitor thread started.")

    return True

def handle_shutdown(signum, frame):
    """
    Gracefully handles shutdown signals (e.g., from Render).
    """
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    shutdown_requested.set() # Set the event to signal threads to stop

# Register the signal handler
signal.signal(signal.SIGTERM, handle_shutdown)

# --- Flask Routes ---

@app.route("/")
def home():
    """
    A simple home route to check if the app is running.
    """
    logger.info("Home route accessed.")
    return "Trading Bot is running!"

@app.route("/ping")
def ping():
    """
    A health check endpoint used by monitoring services like UptimeRobot.
    Checks the status of the bot's core components.
    """
    health = {
        "status": "ok",
        "kite_connect_status": "connected" if kite else "disconnected",
        "monitor_thread_running": threading.main_thread().is_alive(), # Check if the main thread is active
        "current_position": current_position
    }

    if not kite:
        health["status"] = "error"
        return jsonify(health), 503 # Service Unavailable
    
    return jsonify(health)

@app.route("/webhook", methods=["POST"])
def handle_webhook():
    """
    This endpoint receives and processes webhook alerts from TradingView.
    """
    data = request.get_json()
    logger.info(f"Received webhook alert: {data}")

    # Check for an active position to prevent multiple entries
    if current_position.get("active"):
        logger.warning("Active position exists. Ignoring new webhook signal.")
        return jsonify({"status": "ignored", "message": "Position is already active."}), 200

    # Validate webhook secret (no longer in config)

    # --- Entry Logic ---
    signal_type = data.get("signal", "").upper()
    
    if signal_type in ["LONG", "SHORT"]:
        try:
            if is_bullish_crossover(kite, current_position["symbol"]):
                logger.info(f"MACD condition met for a {signal_type} trade.")
                # We can call place_order() with the correct parameters
                # For this example, let's just log it and assume a successful placement
                # place_order(signal_type)
                current_position.update({
                    "active": True,
                    "side": signal_type,
                    "entry_price": 800.00, # Mock price for now
                    "quantity": 750,
                    "initial_sl": 790.00 # Mock SL
                })
                logger.info("Webhook processed. New position placed.")
                return jsonify({"status": "success", "message": f"Position placed: {signal_type}"}), 200
            else:
                logger.warning(f"MACD condition not met for {signal_type} signal. Ignoring.")
                return jsonify({"status": "ignored", "message": "MACD condition not met."}), 200
        
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    else:
        logger.warning(f"Invalid signal type received: {signal_type}")
        return jsonify({"status": "error", "message": "Invalid signal type."}), 400

# --- Main Entry Point ---
if __name__ == "__main__":
    # Perform all critical setup before running the Flask app
    if initialize_bot():
        # Use gunicorn on Render, but Flask's built-in server for local testing
        if os.environ.get("RENDER"):
            # Gunicorn will be used to run the app in production
            pass 
        else:
            app.run(host='0.0.0.0', port=5000, debug=False)
    else:
        logger.critical("Bot initialization failed. Exiting.")
        sys.exit(1)
