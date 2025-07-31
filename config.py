# config.py
from kiteconnect import KiteConnect
import os
import logging

logger = logging.getLogger(__name__)

# --- Environment Variable Loading ---
API_KEY = os.getenv("KITE_API_KEY")
ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

# --- KiteConnect Initialization ---
kite = None
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
SL_PERCENT = 0.0075
TSL_PERCENT = 0.0075

# --- Database File Name ---
DB_FILE_NAME = 'price_track.db'

# --- Google Cloud Storage (GCS) Configuration ---
# This is the path where Render mounts your service account file.
SERVICE_ACCOUNT_FILE = '/etc/secrets/credentials.json'

# This is the name of the GCS bucket you just created.
# It should be set as an environment variable in Render.
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME") # Removed default value as it should always be set via ENV

# --- Check for existence of crucial files/vars at startup ---
if not os.path.exists(SERVICE_ACCOUNT_FILE):
    logger.critical(f"Google Service Account file NOT found at expected path: {SERVICE_ACCOUNT_FILE}. GCS sync will likely fail.")
    SERVICE_ACCOUNT_FILE = None # Set to None to prevent further attempts if file is missing
else:
    logger.info(f"Google Service Account file found at: {SERVICE_ACCOUNT_FILE}")

if not GCS_BUCKET_NAME: # Check if the environment variable was actually loaded
    logger.critical("GCS_BUCKET_NAME environment variable is not set. Google Cloud Storage sync may not work as expected.")
    # You might want to set GCS_BUCKET_NAME = None here too if you want to explicitly halt GCS operations if not set.
    # For now, leaving it as is, as the gcs_sync.py module will handle the None check.


# --- Global Position Tracker ---
current_position = {
    "symbol": None,
    "side": None,
    "entry_price": None,
    "stop_loss": None,
    "effective_stop_loss": None,
    "quantity": None,
    "active": False
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
        "effective_stop_loss": float(stop_loss)
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
