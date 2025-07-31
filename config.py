import os
import logging
from kiteconnect import KiteConnect

# --- Configure Logging for config.py (optional, but good practice) ---
# This logger is specific to config.py, separate from app.py's logger
config_logger = logging.getLogger(__name__)
config_logger.setLevel(logging.INFO)
# Add a handler if you want config messages to go to a separate stream/file
# For simplicity, if basicConfig is already set in app.py, this will use that.


# --- Sensitive Configuration: Load from Environment Variables ---

# Kite Connect API Keys
# IMPORTANT: Set these as environment variables on Render!
# e.g., KITE_API_KEY, KITE_API_SECRET
KITE_API_KEY = os.environ.get("KITE_API_KEY")
KITE_API_SECRET = os.environ.get("KITE_API_SECRET")
KITE_REQUEST_TOKEN = os.environ.get("KITE_REQUEST_TOKEN") # If you're using a request token flow
KITE_ACCESS_TOKEN = os.environ.get("KITE_ACCESS_TOKEN") # If you're using a persistent access token

# TradingView Webhook Secret
# IMPORTANT: Set this as an environment variable on Render!
# e.g., WEBHOOK_SECRET
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")

# Google Cloud Storage related environment variables
# GCS_BUCKET_NAME: The name of your GCS bucket
# GOOGLE_APPLICATION_CREDENTIALS: This environment variable should point to the
#                                 service account JSON key file. Render's Secret Files
#                                 feature is ideal for setting this path.
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")

# Note: SERVICE_ACCOUNT_FILE and GDRIVE_FOLDER_ID are removed as we are now using GCS.
# The `google-cloud-storage` library automatically uses GOOGLE_APPLICATION_CREDENTIALS
# which should be set via Render's Secret Files.


# --- Initialize Kite Connect (only if all necessary credentials are available) ---
kite = None
if KITE_API_KEY and KITE_API_SECRET:
    try:
        kite = KiteConnect(api_key=KITE_API_KEY)
        # If you have a persistent access token, set it here.
        # Otherwise, you'll need a separate login flow to generate it.
        if KITE_ACCESS_TOKEN:
            kite.set_access_token(KITE_ACCESS_TOKEN)
            config_logger.info("KiteConnect initialized with access token.")
        else:
            config_logger.warning("KiteConnect initialized, but no access token provided. "
                                  "Ensure login flow is handled or access token is set.")
    except Exception as e:
        config_logger.error(f"Error initializing KiteConnect: {e}", exc_info=True)
        kite = None # Ensure kite is None if initialization fails
else:
    config_logger.warning("Kite API Key or Secret missing. KiteConnect will not be initialized.")


# --- Global State Management ---
# This dictionary will hold the current position status.
# It's a mutable object, so changes made to it in other modules will be reflected globally.
current_position = {
    "active": False,
    "symbol": None,
    "direction": None, # "LONG" or "SHORT"
    "entry_price": 0.0,
    "quantity": 0,
    "order_id": None,
    # Add other relevant position details as needed (e.g., stop loss, target)
}
config_logger.info(f"Initial current_position state: {current_position}")


# --- Other Non-Sensitive Configurations (Examples) ---
# You can add other configurations here that don't need to be secret
TRADE_QUANTITY = int(os.environ.get("TRADE_QUANTITY", 1)) # Default to 1 if not set
SLIPPAGE_TOLERANCE_PERCENT = float(os.environ.get("SLIPPAGE_TOLERANCE_PERCENT", 0.1)) # 0.1%

# Database file name (e.g., for SQLite)
# This can be a relative path, e.g., 'data/price_track.db'
DB_FILE_NAME = os.environ.get("DB_FILE_NAME", "price_track.db")

# Stop Loss and Trailing Stop Loss percentages
# These could also be environment variables if you want to change them without code deploy
SL_PERCENT = float(os.environ.get("SL_PERCENT", 0.01)) # Example: 1% initial stop loss
TSL_PERCENT = float(os.environ.get("TSL_PERCENT", 0.005)) # Example: 0.5% trailing stop loss

# New: Historical data and MACD calculation parameters
HISTORICAL_DAYS_BACK = int(os.environ.get("HISTORICAL_DAYS_BACK", 7)) # Days of historical data to fetch
CANDLE_INTERVAL = os.environ.get("CANDLE_INTERVAL", "30minute") # Interval for historical candles
MACD_MIN_CANDLES = int(os.environ.get("MACD_MIN_CANDLES", 26)) # Minimum candles required for MACD calculation

config_logger.info(f"Trade quantity: {TRADE_QUANTITY}")
config_logger.info(f"Slippage tolerance: {SLIPPAGE_TOLERANCE_PERCENT}%")
config_logger.info(f"Database file name: {DB_FILE_NAME}")
config_logger.info(f"Initial Stop Loss percentage: {SL_PERCENT * 100}%")
config_logger.info(f"Trailing Stop Loss percentage: {TSL_PERCENT * 100}%")
config_logger.info(f"Historical days back: {HISTORICAL_DAYS_BACK}")
config_logger.info(f"Candle interval: {CANDLE_INTERVAL}")
config_logger.info(f"MACD minimum candles: {MACD_MIN_CANDLES}")
