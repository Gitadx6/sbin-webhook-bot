import os
import threading
import time
import logging
import traceback
import signal # Added for graceful shutdown
from werkzeug.exceptions import BadRequest # Added for specific JSON parsing error handling

from flask import Flask, request, jsonify
# Ensure these imports are correct and available in your environment
from config import kite, current_position, WEBHOOK_SECRET
from symbol_resolver import resolve_sbin_future # Import the symbol resolver
from histogram import fetch_histogram
from order_manager import place_order # Import your custom place_order function
from monitor import start_monitor # The main monitoring loop
from position_manager import fetch_existing_position # To check for existing positions on startup
from gcs_sync import get_gcs_client, upload_file_to_gcs # Import GCS client for health check and final upload


# --- Configuration and Initialization ---

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Flag to indicate if shutdown is requested (for graceful shutdown)
shutdown_requested = threading.Event()

def handle_shutdown_signal(signum, frame):
    """Handler for system termination signals."""
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    shutdown_requested.set() # Set the event to signal threads to stop

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, handle_shutdown_signal)  # Ctrl+C
signal.signal(signal.SIGTERM, handle_shutdown_signal) # Sent by orchestration systems like Render


# Function to run once when the application starts
def initialize_bot():
    """
    Performs initial setup tasks for the bot.
    This includes downloading necessary files and checking existing positions.
    """
    logger.info("Starting bot initialization...")

    try:
        # 1. File download and DB initialization are handled by monitor's startup sequence.
        # The monitor_loop itself will call download_file_from_gcs() and init_db().
        logger.info("File download and DB initialization handled by monitor startup.")
    except Exception as e:
        logger.error(f"Error during initial setup: {e}", exc_info=True)
        # Depending on criticality, you might want to exit here or continue with a warning

    # 2. Check for existing positions on startup.
    # This will update current_position if a trade is found.
    if fetch_existing_position():
        logger.info("✅ Existing SBIN position found. Monitoring for exit...")
    else:
        logger.info("🔍 No open position found. Waiting for TradingView signal to enter trade.")

    # 3. Start the monitor in a separate thread.
    # This assumes start_monitor() is a long-running, blocking function.
    # It's crucial that this runs in a separate thread to not block the Flask app.
    logger.info("Starting monitor in a background thread...")
    monitor_thread = threading.Thread(target=start_monitor, daemon=True, name="MonitorThread")
    monitor_thread.start()
    logger.info("Monitor thread started.")

    # 4. Start the auto-position checker in a separate thread.
    # This thread periodically calls fetch_existing_position to re-check for positions.
    logger.info("Starting auto-position checker in a background thread...")
    position_checker_thread = threading.Thread(target=auto_position_checker, daemon=True, name="PositionCheckerThread")
    position_checker_thread.start()
    logger.info("Auto-position checker thread started.")

    logger.info("Bot initialization complete.")

# Background thread to periodically check for existing positions
def auto_position_checker():
    """
    Periodically checks for existing trading positions and updates global state.
    Runs as a daemon thread.
    """
    logger.info("Auto-position checker thread started.")
    while not shutdown_requested.is_set(): # Check shutdown flag
        try:
            # Only check if no position is currently active according to our state
            if not current_position.get("active", False): # Use .get with default for safety
                logger.debug("No active position detected, checking for existing position...")
                found = fetch_existing_position()
                if found:
                    logger.info("🔁 Position auto-detected. Monitoring for exit...", flush=True)
            else:
                logger.debug("Active position found, skipping auto-check for existing position.")
        except Exception as e:
            logger.error(f"Error in auto_position_checker: {e}", exc_info=True)
        time.sleep(60)  # Check every 60 seconds
    logger.info("Auto-position checker thread stopped.")


# Call the initialization function when the app context is ready.
# For Gunicorn/Render, the `initialize_bot()` function will be called
# when the application instance is loaded.
initialize_bot()


# --- Flask Routes ---

@app.route("/", methods=["GET"])
def home():
    """
    Home route to confirm the bot is live.
    """
    logger.info("Home route accessed.")
    return "✅ SBIN Trading Bot is Live!"

@app.route("/ping", methods=["GET"])
def ping():
    """
    Comprehensive health check endpoint.
    Checks connectivity to Kite, GCS, and internal bot state.
    """
    health_status = {"status": "healthy", "checks": {}}
    
    # Check KiteConnect connectivity
    try:
        # Attempt a lightweight Kite API call, e.g., fetching profile
        # This requires the Kite object to be correctly authenticated in config.py
        user_profile = kite.profile()
        health_status["checks"]["kite_connect"] = {"status": "ok", "user_id": user_profile.get("user_id")}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["kite_connect"] = {"status": "error", "message": str(e)}

    # Check GCS connectivity (by trying to get a client)
    gcs_client = get_gcs_client()
    if gcs_client:
        health_status["checks"]["gcs_storage"] = {"status": "ok"}
    else:
        health_status["status"] = "unhealthy"
        health_status["checks"]["gcs_storage"] = {"status": "error", "message": "GCS client initialization failed or not available"}

    # Check if current_position is in a valid state (e.g., active or inactive correctly)
    health_status["checks"]["bot_state_active_position"] = {
        "status": "ok",
        "active": current_position.get("active", False),
        "symbol": current_position.get("symbol")
    }
    
    # Check if monitor thread is alive
    monitor_thread_alive = False
    for t in threading.enumerate():
        if t.name == "MonitorThread" and t.is_alive():
            monitor_thread_alive = True
            break
    health_status["checks"]["monitor_thread"] = {"status": "ok" if monitor_thread_alive else "error"}
    if not monitor_thread_alive:
        health_status["status"] = "unhealthy"
        health_status["checks"]["monitor_thread"]["message"] = "Monitor thread is not running."

    # Check if position checker thread is alive
    position_checker_thread_alive = False
    for t in threading.enumerate():
        if t.name == "PositionCheckerThread" and t.is_alive():
            position_checker_thread_alive = True
            break
    health_status["checks"]["position_checker_thread"] = {"status": "ok" if position_checker_thread_alive else "error"}
    if not position_checker_thread_alive:
        health_status["status"] = "unhealthy"
        health_status["checks"]["position_checker_thread"]["message"] = "Position checker thread is not running."


    logger.info(f"Health check performed: {health_status['status']}")
    return jsonify(health_status), 200 if health_status["status"] == "healthy" else 500


@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Receives and processes TradingView webhook signals.
    This is the main entry point for trade signals.
    """
    try:
        data = request.get_json(force=True)
        logger.info(f"📩 Webhook received: {data}")

        # Verify secret key for security
        if data.get("secret") != WEBHOOK_SECRET:
            logger.warning(f"❌ Invalid secret key received from {request.remote_addr}!")
            return jsonify({"status": "unauthorized", "message": "Invalid secret key"}), 403

        direction = data.get("direction", "").upper()
        price = float(data.get("price", 0))

        # Test signal to verify connectivity
        if direction == "TEST":
            logger.info("🧪 Test webhook received successfully.")
            return jsonify({"status": "ok", "message": "Test successful"}), 200

        # Proceed only if LONG/SHORT
        if direction not in ["LONG", "SHORT"]:
            logger.warning(f"⚠️ Unknown direction received: {direction}")
            return jsonify({"status": "ignored", "reason": "Invalid direction"}), 400

        # --- Core Trading Logic ---
        # 1. Resolve the correct SBIN future symbol
        symbol = resolve_sbin_future() # This will get the current month's or next month's future
        if not symbol:
            logger.error("❌ Could not resolve SBIN future symbol. Skipping trade entry.")
            return jsonify({"status": "error", "reason": "Symbol resolution failed"}), 500

        # 2. Fetch histogram data for strategy validation
        result, status = fetch_histogram(symbol)
        if status != "ok" or result is None:
            logger.error(f"❌ Histogram fetch failed for {symbol}, skipping trade entry. Status: {status}")
            return jsonify({"status": "error", "reason": "Histogram fetch failed"}), 500

        hist = result["hist"]
        cross_to_green = result["cross_to_green"]
        cross_to_red = result["cross_to_red"]

        # 3. Confirm flip condition based on strategy
        if direction == "LONG" and not (hist > 0 and cross_to_green):
            logger.info("⛔ No green flip, ignoring LONG entry.")
            return jsonify({"status": "ignored", "reason": "No green flip"})
        if direction == "SHORT" and not (hist < 0 and cross_to_red):
            logger.info("⛔ No red flip, ignoring SHORT entry.")
            return jsonify({"status": "ignored", "reason": "No red flip"})

        # 4. Place the order using your order_manager function
        # This function will also update current_position and initialize price_tracker
        order_id = place_order(symbol, direction, price)
        if order_id:
            logger.info(f"✅ Order placed and position updated: {order_id}")
            return jsonify({"status": "success", "order_id": order_id})
        else:
            logger.error("❌ Order placement failed via order_manager.")
            return jsonify({"status": "error", "reason": "Order placement failed"}), 500

    except BadRequest as e: # Specific error for invalid JSON
        logger.error(f"❌ Webhook JSON parsing error: {e.description}\n{traceback.format_exc()}")
        return jsonify({"status": "error", "message": "Invalid JSON format in request body"}), 400
    except ValueError as ve:
        logger.error(f"❌ Webhook data parsing error (value conversion): {ve}\n{traceback.format_exc()}")
        return jsonify({"status": "error", "message": "Invalid data format or type"}), 400
    except Exception as e:
        logger.critical(f"❌ Unhandled webhook error: {e}\n{traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/test", methods=["POST"])
def test_alert():
    """
    Endpoint to receive and log test alerts from TradingView.
    This is useful for verifying webhook connectivity.
    """
    try:
        data = request.get_json(force=True)
        logger.info(f"✅ Test alert received from TradingView: {data}")
        return jsonify({"status": "test success", "data": data})
    except Exception as e:
        logger.error(f"❌ Error processing test alert: {e}\n{traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Entry Point for Render/Gunicorn ---
# This block is for local testing. On Render, you will use a WSGI server like Gunicorn.
# Your Render 'start command' would be something like: `gunicorn app:app`
if __name__ == "__main__":
    logger.info("Running Flask app in development mode.")
    try:
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    except Exception as e:
        logger.critical(f"Flask app experienced an unexpected error: {e}\n{traceback.format_exc()}")
    finally:
        # This block will execute when the Flask app shuts down
        logger.info("Main application shutting down. Attempting final upload of price_track.db...")
        upload_file_to_gcs() # This calls the upload_file_to_gcs from gcs_sync.py
        logger.info("Final upload attempt complete.")

logger.info("🚀 Deployed version 1.2 (Integrated)")
