# config.py
from kiteconnect import KiteConnect
import os
import logging
# No need for 'json' import anymore as Render directly mounts the file

# Configure logging for this module
logger = logging.getLogger(__name__)

# --- Environment Variable Loading ---
# These variables should be set directly in your Render service's environment.
API_KEY = os.getenv("KITE_API_KEY")
ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") # If you use webhooks

# --- KiteConnect Initialization ---
kite = None # Initialize kite to None
if not API_KEY or not ACCESS_TOKEN:
    logger.critical("KITE_API_KEY or KITE_ACCESS_TOKEN environment variables are not set. KiteConnect will not be initialized.")
else:
    try:
        kite = KiteConnect(api_key=API_KEY)
        kite.set_access_token(ACCESS_TOKEN)
        logger.info("KiteConnect initialized successfully.")
    except Exception as e:
        logger.critical(f"Error initializing KiteConnect: {e}. Check API key and access token. KiteConnect not available.")

# --- Trading Parameters ---
SL_PERCENT = 0.0075     # 0.75% Stop Loss
TSL_PERCENT = 0.0075    # 0.75% Trailing Stop Loss

# --- Database File Name (for price_tracker.py and gdrive_sync.py) ---
DB_FILE_NAME = 'price_track.db' # This file will be in the root of your project directory or a specified data dir

# --- Google Drive Configuration ---
# Set this to the exact path where Render mounts your secret service account file.
# Based on your Render explanation, it's /etc/secrets/credentials.json
SERVICE_ACCOUNT_FILE = '/etc/secrets/credentials.json'

# Google Drive folder ID where your DB is stored (also from environment variable)
GDRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "YOUR_DEFAULT_GDRIVE_FOLDER_ID") # REMEMBER TO CHANGE THIS DEFAULT ONCE

# --- Check for existence of crucial files/vars at startup ---
if not os.path.exists(SERVICE_ACCOUNT_FILE):
    logger.critical(f"Google Service Account file NOT found at expected path: {SERVICE_ACCOUNT_FILE}. Google Drive sync will likely fail.")
    # Set to None to prevent further errors attempting to use a non-existent file
    SERVICE_ACCOUNT_FILE = None
if not GDRIVE_FOLDER_ID or GDRIVE_FOLDER_ID == "YOUR_DEFAULT_GDRIVE_FOLDER_ID":
    logger.critical("GOOGLE_DRIVE_FOLDER_ID environment variable is not set or is still default. Google Drive sync may not work as expected.")


# --- Global Position Tracker ---
current_position = {
    "symbol": None,
    "side": None,
    "entry_price": None,
    "stop_loss": None,          # Initial fixed stop loss
    "effective_stop_loss": None,# Dynamic stop loss (initial or trailed)
    "quantity": None,
    "active": False             # Whether a position is currently active
}

def resolve_token(symbol):
    """Resolves instrument token for a given trading symbol."""
    if kite is None:
        raise Exception("KiteConnect is not initialized. Cannot resolve instrument token.")
    
    try:
        instruments = kite.instruments("NFO")
    except Exception as e:
        logger.error(f"Error fetching instruments from Kite: {e}")
        raise Exception(f"Failed to fetch instruments: {e}")

    for item in instruments:
        if item["tradingsymbol"] == symbol:
            logger.info(f"Resolved {symbol} to token {item['instrument_token']}")
            return item["instrument_token"]
    logger.error(f"Instrument token not found for symbol: {symbol}")
    raise Exception(f"Instrument token not found for symbol: {symbol}")

def set_active_position(symbol, side, entry_price, stop_loss, quantity=750):
    """
    Sets or updates the current active position.
    This function should be called by your order placement logic.
    """
    # Validate that stop_loss is not None for numerical operations
    if not all([symbol, side, entry_price, stop_loss is not None]):
        logger.error(f"Attempted to set active position with incomplete or invalid data: {symbol=}, {side=}, {entry_price=}, {stop_loss=}")
        return False

    current_position.update({
        "active": True,
        "symbol": symbol,
        "side": side,
        "entry_price": float(entry_price),
        "stop_loss": float(stop_loss),
        "quantity": int(quantity),
        "effective_stop_loss": float(stop_loss) # Initialize effective SL with the initial stop loss
    })
    logger.info(f"Active position set: {current_position}")
    return True

def clear_active_position():
    """Clears the active position, typically called after an exit."""
    current_position.update({
        "symbol": None,
        "side": None,
        "entry_price": None,
        "stop_loss": None,
        "effective_stop_loss": None,
        "quantity": None,
        "active": False
    })
    logger.info("Active position cleared.")
