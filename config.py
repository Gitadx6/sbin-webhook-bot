import os
import logging
import threading
from kiteconnect import KiteConnect

# --- Configuration Constants ---
# Use environment variables for sensitive or deployment-specific settings
KITE_API_KEY = os.environ.get("KITE_API_KEY")
KITE_API_SECRET = os.environ.get("KITE_API_SECRET")
KITE_ACCESS_TOKEN = os.environ.get("KITE_ACCESS_TOKEN")

# Trading instrument
# This defines the base index (e.g., "NIFTY") that the symbol_resolver.py
# will use to find the correct futures contract.
Instrument = "SBIN"

# Bot settings
# The lot size for SBIN futures is 750
TRADE_QUANTITY = int(os.environ.get("TRADE_QUANTITY", 750))
monitor_frequency = float(os.environ.get("MONITOR_FREQUENCY", 15.0))  # seconds

# Time interval for chart data used by indicators (e.g., "minute", "3minute", "5minute", "15minute")
TIME_INTERVAL = os.environ.get("TIME_INTERVAL", "5minute")

# Stop Loss and Trailing Stop Loss configurations
# We use both a percentage-based and a fixed-point TSL for different logic
SL_PERCENT = float(os.environ.get("SL_PERCENT", 0.01)) # 1% initial stop loss for calculations
TSL_PERCENT = float(os.environ.get("TSL_PERCENT", 0.005)) # 0.5% trailing stop loss for calculations
TSL_TRAIL_AMOUNT = float(os.environ.get("TSL_TRAIL_AMOUNT", 6.0)) # ₹ per share for fixed TSL

# Database and synchronization settings
DB_FILE_NAME = "bot_state.json"
DB_LOCK_FILE = "bot_state.lock"
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")

# --- Global Variables ---
# Global object for KiteConnect client
kite = None

# Global dictionary to store the current position state
current_position = {
    "symbol": "",
    "token": None,
    "side": "NONE",
    "active": False,
    "quantity": 0,
    "entry_price": 0.0,
    "initial_sl": 0.0,
    "effective_sl": None, # Will be set to initial_sl on first monitor tick
}

# Event object to signal a graceful shutdown
shutdown_requested = threading.Event()

# --- Logging Setup ---
# A common logger for all modules to ensure consistent output
config_logger = logging.getLogger(__name__)

# --- KiteConnect Initialization ---
# This block initializes the KiteConnect object only if credentials are provided.
if KITE_API_KEY and KITE_API_SECRET:
    try:
        kite = KiteConnect(api_key=KITE_API_KEY)
        if KITE_ACCESS_TOKEN:
            kite.set_access_token(KITE_ACCESS_TOKEN)
            config_logger.info("KiteConnect initialized with access token.")
        else:
            config_logger.warning("Kite API Access Token is missing. Only `KiteConnect` object is initialized. You need to provide an access token to make API calls.")
    except Exception as e:
        config_logger.error(f"Error initializing KiteConnect: {e}", exc_info=True)
        kite = None
else:
    config_logger.warning("Kite API Key or Secret missing. KiteConnect will not be initialized.")

# --- Local Testing with Request Token (Optional) ---
# If you are running locally without an access token, you can use this section
# to generate one. This is not for a production environment like Render.
if not KITE_ACCESS_TOKEN and not os.environ.get("RENDER"):
    config_logger.warning("No access token found. To generate one locally:")
    config_logger.warning("1. Get a request token from the following URL:")
    config_logger.warning(kite.login_url())
    config_logger.warning("2. Run a separate script with the request token to get the access token.")
