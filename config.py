import os
import logging
import threading
from kiteconnect import KiteConnect
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Credentials ---
# Ensure these environment variables are set correctly on Render
api_key = os.environ.get("KITE_API_KEY")
access_token = os.environ.get("KITE_ACCESS_TOKEN")

# --- KiteConnect Client Setup ---
try:
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
except Exception as e:
    logging.error(f"Failed to initialize KiteConnect client: {e}")
    kite = None

# --- Global Trading Parameters ---
# The symbol you want to trade
Instrument = "RELIANCE"

# The quantity for each trade
TRADE_QUANTITY = 1

# The time interval for the candles (e.g., "5minute", "10minute", "15minute")
TIME_INTERVAL = "5minute"

# --- Strategy Parameters ---
# RSI settings
RSI_PERIOD = 14

# ATR settings
ATR_PERIOD = 14
ATR_MULTIPLIER = 2.0

# Trailing Stop Loss settings
TRAILING_STOP_MULTIPLIER = 1.0

# --- Global State Dictionaries ---
# This dictionary will hold the state of the current position.
# We are no longer loading this from a file.
current_position = {
    "symbol": None,
    "token": None,
    "side": None,
    "active": False,
    "quantity": 0,
    "entry_price": 0,
    "initial_sl": 0,
    "effective_sl": 0
}

# Threading event for graceful shutdown
shutdown_requested = threading.Event()
