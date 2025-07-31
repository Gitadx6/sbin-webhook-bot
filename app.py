import os
import threading
import time
import logging

from flask import Flask, request, jsonify
# Ensure these imports are correct and available in your environment
from config import kite, current_position, WEBHOOK_SECRET
from symbol_resolver import resolve_sbin_future
from histogram import fetch_histogram
from order_manager import place_order
from monitor import start_monitor
from position_manager import fetch_existing_position
from gdrive_sync import download_file # Assuming this handles GCS interaction


# --- Configuration and Initialization ---

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Background Tasks and Startup Logic ---

# Function to run once when the application starts
def initialize_bot():
    """
    Performs initial setup tasks for the bot.
    This includes downloading necessary files and checking existing positions.
    """
    logger.info("Starting bot initialization...")

    try:
        # 1. Download necessary files from Google Cloud Storage
        # This should ideally be non-blocking or handled robustly.
        # If it's critical for the app to run, consider making it blocking here
        # but ensure it has proper error handling and retries.
        logger.info("Attempting to download configuration/data files...")
        download_file() # Ensure this function handles its own errors or raises them
        logger.info("File download complete.")
    except Exception as e:
        logger.error(f"Error during file download: {e}", exc_info=True)
        # Depending on criticality, you might want to exit here or continue with a warning
        # For a trading bot, this could be critical.

    # 2. Check for existing positions on startup
    if fetch_existing_position():
        logger.info("✅ Existing SBIN position found. Monitoring for exit...")
        # No need to set current_position["active"] here if fetch_existing_position
        # already updates it. Ensure it does.
    else:
        logger.info("🔍 No open position found. Waiting for TradingView signal to enter trade.")

    # 3. Start the monitor in a separate thread
    # This assumes start_monitor() is a long-running, blocking function.
    # It's crucial that this runs in a separate thread to not block the Flask app.
    logger.info("Starting monitor in a background thread...")
    monitor_thread = threading.Thread(target=start_monitor, daemon=True)
    monitor_thread.start()
    logger.info("Monitor thread started.")

    # 4. Start the auto-position checker in a separate thread
    logger.info("Starting auto-position checker in a background thread...")
    position_checker_thread = threading.Thread(target=auto_position_checker, daemon=True)
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
    while True:
        try:
            # Only check if no position is currently active according to our state
            if not current_position.get("active", False): # Use .get with default for safety
                logger.debug("No active position detected, checking for existing position...")
                found = fetch_existing_position()
                if found:
                    logger.info("🔁 Position auto-detected. Monitoring for exit...")
            else:
                logger.debug("Active position found, skipping auto-check for existing position.")
        except Exception as e:
            logger.error(f"Error in auto_position_checker: {e}", exc_info=True)
        time.sleep(60)  # Check every 60 seconds

# Call the initialization function when the app context is ready.
# For Flask, this can be done using a decorator or by calling it
# before `app.run()` if using a WSGI server.
# For Gunicorn/Render, the `initialize_bot()` function will be called
# when the application instance is loaded.
# A common pattern is to call it within __name__ == "__main__" or
# rely on the WSGI server's entry point.
# For simplicity, we'll call it directly here, assuming it runs once.
# In a real Gunicorn setup, you might use a pre-load hook or a Flask app context hook.
# For Render, the entrypoint command (e.g., `gunicorn app:app`) will execute this file.
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
    Basic health check endpoint.
    """
    logger.info("Ping route accessed.")
    return jsonify({"status": "alive"})

@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Receives and processes TradingView webhook signals.
    """
    try:
        data = request.get_json(force=True)
        logger.info(f"📩 Webhook received: {data}")

        # Verify secret key
        # IMPORTANT: WEBHOOK_SECRET should be an environment variable on Render!
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

        symbol = resolve_sbin_future()

        # Fetch histogram data
        result, status = fetch_histogram(symbol)

        if status != "ok" or result is None:
            logger.error(f"❌ Histogram fetch failed for {symbol}, skipping trade entry. Status: {status}")
            return jsonify({"status": "error", "reason": "Histogram fetch failed"}), 500

        hist = result["hist"]
        cross_to_green = result["cross_to_green"]
        cross_to_red = result["cross_to_red"]

        # Confirm flip condition
        if direction == "LONG" and not (hist > 0 and cross_to_green):
            logger.info("⛔ No green flip, ignoring LONG entry.")
            return jsonify({"status": "ignored", "reason": "No green flip"})
        if direction == "SHORT" and not (hist < 0 and cross_to_red):
            logger.info("⛔ No red flip, ignoring SHORT entry.")
            return jsonify({"status": "ignored", "reason": "No red flip"})

        order_id = place_order(symbol, direction, price)
        logger.info(f"✅ Order placed: {order_id}")
        return jsonify({"status": "success", "order_id": order_id})

    except ValueError as ve:
        logger.error(f"❌ Webhook data parsing error: {ve}", exc_info=True)
        return jsonify({"status": "error", "message": "Invalid data format"}), 400
    except Exception as e:
        logger.error(f"❌ Unhandled webhook error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Entry Point for Render/Gunicorn ---
# This block is for local testing. On Render, you will use a WSGI server like Gunicorn.
# Your Render 'start command' would be something like: `gunicorn app:app`
if __name__ == "__main__":
    # For local development, you can run: python app.py
    # For production, use Gunicorn: gunicorn app:app
    logger.info("Running Flask app in development mode.")
    app.run(host="0.0.0.0", port=os.environ.get("PORT", 10000))
