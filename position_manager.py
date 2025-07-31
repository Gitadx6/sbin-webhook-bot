import json
import os
import threading
import logging
import traceback

from config import DB_FILE_NAME, DB_LOCK_FILE

# Configure logging for this module
logger = logging.getLogger(__name__)

def save_position(position_data):
    """
    Saves the current position data to a local JSON file.
    Uses a lock file to prevent multiple processes from writing at the same time.
    """
    lock_path = DB_LOCK_FILE
    
    # Wait for the lock to be released
    while os.path.exists(lock_path):
        logger.debug("Waiting for DB lock to be released...")
        time.sleep(0.5)

    # Create the lock file
    try:
        with open(lock_path, 'w') as f:
            f.write('')
        logger.debug("DB lock acquired.")
    except IOError as e:
        logger.error(f"Failed to acquire DB lock: {e}")
        return False

    try:
        with open(DB_FILE_NAME, 'w') as f:
            json.dump(position_data, f, indent=4)
        logger.info(f"Position data saved to '{DB_FILE_NAME}'.")
        return True
    except IOError as e:
        logger.error(f"Error writing to database file: {e}")
        return False
    finally:
        # Release the lock
        try:
            os.remove(lock_path)
            logger.debug("DB lock released.")
        except OSError as e:
            logger.error(f"Failed to release DB lock: {e}")

def fetch_existing_position():
    """
    Fetches the last known position data from the local JSON file.
    Returns the position dictionary if the file exists, otherwise returns None.
    """
    if not os.path.exists(DB_FILE_NAME):
        logger.info(f"Database file '{DB_FILE_NAME}' not found. No existing position.")
        return None
        
    lock_path = DB_LOCK_FILE

    # Wait for the lock to be released before reading
    while os.path.exists(lock_path):
        logger.debug("Waiting for DB lock to be released before reading...")
        time.sleep(0.5)

    try:
        with open(DB_FILE_NAME, 'r') as f:
            position_data = json.load(f)
        return position_data
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Error reading or decoding database file: {e}")
        return None

