import os
import sys
import json
import logging
import threading
import time
import datetime
import traceback
from flask import Flask, request, jsonify

# --- Project-specific Imports ---
from config import kite, DB_FILE_NAME, current_position
from order_manager import place_order
from monitor import monitor_loop
from symbol_resolver import resolve_token
from gcs_sync import download_file_from_gcs
from position_manager import fetch_existing_position
# We have a new function for a bearish crossover, which we will use for short trades.
from macd_indicator import is_bullish_crossover, is_bearish_crossover

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
        # First, try to download the last known position from Google Cloud Storage
        if download_file_from_gcs():
            logger.info("Successfully downloaded position file from GCS.")
            
        # Then, load the position from the local file
        db_position = fetch_existing_position()
        if db_position:
            current_position.update(db_position)
            logger.info("Loaded existing position from local DB.")
        else:
            logger.info("No existing position found. Starting fresh.")
            # Initialize with default values if no position is found
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
        logger.error(f"Error during state initialization: {e}\n{traceback.format_exc()}")
        # Fallback to an empty position dictionary if something goes wrong
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
    Handles incoming webhooks from TradingView or a similar platform.
    This is where the bot receives trade signals.
    """
    global current_position

    try:
        data = request.json
        logger.info("Received webhook data: %s", data)
        
        # We check for a password to ensure the webhook is coming from a trusted source
        if data.get("password") != os.environ.get("WEBHOOK_PASSWORD"):
            logger.warning("Unauthorized webhook access attempt.")
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
        symbol = data.get("symbol")
        timeframe = data.get("timeframe")
        
        # Fetch historical data to run the MACD logic
        try:
            instrument_token = resolve_token(symbol)
            if not instrument_token:
                return jsonify({"status": "error", "message": f"Could not resolve symbol {symbol}"}), 400
                
            from_date = datetime.datetime.now() - datetime.timedelta(days=35)
            to_date = datetime.datetime.now()
            interval = "minute" if timeframe == "1m" else "3minute" # Example mapping
            
            # Fetch historical data using KiteConnect
            historical_data = kite.historical_data(instrument_token, from_date, to_date, interval, continuous=False, oi=False)
            closing_prices = [item['close'] for item in historical_data]
            
            if not closing_prices:
                return jsonify({"status": "error", "message": f"No historical data found for {symbol}"}), 404
                
        except Exception as e:
            logger.error(f"Failed to fetch historical data for {symbol}: {e}\n{traceback.format_exc()}")
            return jsonify({"status": "error", "message": "Failed to fetch historical data"}), 500

        # --- Trading Logic using MACD Crossovers ---
        
        # Check if there is an active position
        if current_position["active"]:
            logger.info("Already have an active position. Ignoring new signal.")
            return jsonify({"status": "info", "message": "Already in a trade, ignoring signal."})

        # Check for a bullish signal (MACD histogram turning green)
        if is_bullish_crossover(closing_prices):
            logger.info("MACD Bullish Crossover signal received. Placing a long trade.")
            # Place a buy order (LONG trade)
            place_order(symbol=symbol, side="LONG")
            return jsonify({"status": "success", "message": "Bullish signal received. Long trade placed."})

        # Check for a bearish signal (MACD histogram turning red)
        elif is_bearish_crossover(closing_prices):
            logger.info("MACD Bearish Crossover signal received. Placing a short trade.")
            # Place a sell order (SHORT trade)
            place_order(symbol=symbol, side="SHORT")
            return jsonify({"status": "success", "message": "Bearish signal received. Short trade placed."})
            
        else:
            logger.info("No valid MACD crossover signal detected.")
            return jsonify({"status": "info", "message": "No valid signal detected."})

    except Exception as e:
        logger.error("An error occurred in the webhook handler: %s", e, exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

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
