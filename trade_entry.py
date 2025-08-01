import os
import logging
import datetime
import traceback
from flask import jsonify

from config import kite, current_position
from order_manager import place_order
from symbol_resolver import resolve_token
from macd_indicator import is_bullish_crossover, is_bearish_crossover

# Configure logging for this module
logger = logging.getLogger(__name__)

def handle_trade_webhook(data):
    """
    Handles the incoming webhook data from a trading platform, validates it,
    and checks for a valid MACD crossover signal to place a trade.

    Args:
        data (dict): The JSON payload from the webhook.

    Returns:
        tuple: A tuple containing a JSON response and an HTTP status code.
    """
    global current_position

    try:
        # Check for a security password
        if data.get("password") != os.environ.get("WEBHOOK_PASSWORD"):
            logger.warning("Unauthorized webhook access attempt.")
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
        symbol = data.get("symbol")
        timeframe = data.get("timeframe")

        if not symbol or not timeframe:
            logger.warning("Webhook data is missing 'symbol' or 'timeframe'.")
            return jsonify({"status": "error", "message": "Missing symbol or timeframe in webhook."}), 400

        # Check if there is an active position before placing a new one
        if current_position.get("active"):
            logger.info("Already have an active position. Ignoring new signal.")
            return jsonify({"status": "info", "message": "Already in a trade, ignoring signal."}), 200

        # Fetch historical data to run the MACD logic
        try:
            instrument_token = resolve_token(symbol)
            if not instrument_token:
                return jsonify({"status": "error", "message": f"Could not resolve symbol {symbol}"}), 400
                
            from_date = datetime.datetime.now() - datetime.timedelta(days=35)
            to_date = datetime.datetime.now()
            interval = "minute" if timeframe == "1m" else "3minute" # Example mapping
            
            historical_data = kite.historical_data(instrument_token, from_date, to_date, interval, continuous=False, oi=False)
            closing_prices = [item['close'] for item in historical_data]
            
            if not closing_prices:
                return jsonify({"status": "error", "message": f"No historical data found for {symbol}"}), 404
                
        except Exception as e:
            logger.error(f"Failed to fetch historical data for {symbol}: {e}\n{traceback.format_exc()}")
            return jsonify({"status": "error", "message": "Failed to fetch historical data"}), 500

        # Check for a bullish signal (MACD histogram turning green)
        if is_bullish_crossover(closing_prices):
            logger.info("MACD Bullish Crossover signal received. Placing a long trade.")
            place_order(symbol=symbol, side="LONG")
            return jsonify({"status": "success", "message": "Bullish signal received. Long trade placed."}), 200

        # Check for a bearish signal (MACD histogram turning red)
        elif is_bearish_crossover(closing_prices):
            logger.info("MACD Bearish Crossover signal received. Placing a short trade.")
            place_order(symbol=symbol, side="SHORT")
            return jsonify({"status": "success", "message": "Bearish signal received. Short trade placed."}), 200
            
        else:
            logger.info("No valid MACD crossover signal detected.")
            return jsonify({"status": "info", "message": "No valid signal detected."}), 200

    except Exception as e:
        logger.error("An unhandled error occurred in the trade entry logic: %s", e, exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500
