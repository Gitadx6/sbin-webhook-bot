import os
import sys
import logging
import threading
from flask import Flask, request

# --- Project-specific Imports ---
from config import current_position
from monitor import monitor_loop
from gcs_sync import download_file_from_gcs
from position_manager import fetch_existing_position
# Import the new entry logic module
from trade_entry import handle_trade_webhook

# --- Flask App Setup ---
app = Flask(__name__)

# Configure a root logger for the application
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("trading_bot.log"),
                        logging.StreamHandler(sys.stdout)
                    ])

logger = logging.getLogger(__name__)

# --- Initialization and Setup ---
def initialize_state():
    """
    Initializes the bot's state by attempting to download a position from GCS.
    """
    logger.info("Initializing bot state...")
    try:
        if download_file_from_gcs():
            logger.info("Successfully downloaded position file from GCS.")
            
        db_position = fetch_existing_position()
        if db_position:
            current_position.update(db_position)
            logger.info("Loaded existing position from local DB.")
        else:
            logger.info("No existing position found. Starting fresh.")
            current_position.update({
                "active": False,
                "symbol": None,
                "side": None,
                "quantity": 0,
                "entry_price": 0.0,
                "initial_sl": 0.0,
                "effective_sl": None,
                "target": 0.0,
            })
            
    except Exception as e:
        logger.error(f"Error during state initialization: {e}", exc_info=True)
        current_position.update({
            "active": False,
            "symbol": None,
            "side": None,
            "quantity": 0,
            "entry_price": 0.0,
            "initial_sl": 0.0,
            "effective_sl": None,
            "target": 0.0,
        })
        
    logger.info("Current position state after initialization: %s", current_position)

# --- Routes and Webhooks ---

@app.route("/")
def home():
    """A simple homepage for the bot."""
    return "<h1>Trading Bot is Live!</h1><p>Send a webhook to /webhook to place a trade.</p>"

@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Handles incoming webhooks by passing them to the trade entry logic module.
    """
    data = request.json
    return handle_trade_webhook(data)

# --- Main Application Logic ---
if __name__ == "__main__":
    logger.info("Starting the trading bot application...")
    
    # Initialize the position state from local DB or GCS
    initialize_state()

    # Start the monitoring thread in the background
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    logger.info("Background monitoring thread started.")
    
    # Run the Flask app on all available network interfaces
    app.run(host='0.0.0.0', port=5000)
