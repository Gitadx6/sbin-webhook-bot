# config.py
from kiteconnect import KiteConnect
import os
import logging # Import logging

# Initialize logger for this module
logger = logging.getLogger(__name__)

# --- Environment Variable Loading ---
# Ensure python-dotenv is installed (pip install python-dotenv)
# and your .env file is configured and added to .gitignore.
# If running directly on Render, environment variables are typically set in Render's dashboard.
# from dotenv import load_dotenv
# load_dotenv() # Uncomment if you're loading from a local .env file

API_KEY = os.getenv("KITE_API_KEY")
ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") # If you use webhooks

# --- KiteConnect Initialization ---
if not API_KEY or not ACCESS_TOKEN:
    logger.critical("KITE_API_KEY or KITE_ACCESS_TOKEN environment variables are not set. Exiting.")
    # In a real application, you might raise an exception or handle this more gracefully
    # For now, let's make sure 'kite' doesn't cause errors if not initialized.
    kite = None # Set to None to prevent errors if credentials are missing
else:
    try:
        kite = KiteConnect(api_key=API_KEY)
        kite.set_access_token(ACCESS_TOKEN)
        logger.info("KiteConnect initialized successfully.")
    except Exception as e:
        logger.critical(f"Error initializing KiteConnect: {e}. Check API key and access token.")
        kite = None # Set to None on failure


# --- Trading Parameters ---
SL_PERCENT = 0.0075     # 0.75% Stop Loss
TSL_PERCENT = 0.0075    # 0.75% Trailing Stop Loss

# --- Database File Name (for price_tracker.py and gdrive_sync.py) ---
DB_FILE_NAME = 'price_track.db'

# --- Google Drive Configuration (also from environment variables) ---
# It's highly recommended to store the service account key file path and folder ID
# as environment variables on Render for security.
# Example: GOOGLE_SERVICE_ACCOUNT_PATH=/etc/secrets/google_service_account.json
# GOOGLE_DRIVE_FOLDER_ID=your_actual_folder_id
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "path/to/your/service_account.json")
GDRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "your_google_drive_folder_id") # Replace default with your actual ID


# --- Global Position Tracker ---
# Updated to match the expected structure in monitor.py
current_position = {
    "symbol": None,
    "side": None,
    "entry_price": None,
    "stop_loss": None,          # Initial fixed stop loss
    "effective_stop_loss": None,# CRITICAL: This is the dynamic SL (initial SL or TSL)
    "quantity": None,
    "active": False             # Whether a position is currently active
}

def resolve_token(symbol):
    """Resolves instrument token for a given trading symbol."""
    if kite is None:
        raise Exception("KiteConnect is not initialized. Cannot resolve instrument token.")
    
    # Check if instruments are already fetched or fetch them
    # For production, consider caching instruments to avoid repeated API calls
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
    # Validate input
    if not all([symbol, side, entry_price, stop_loss]):
        logger.error("Attempted to set active position with incomplete data.")
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
