import datetime
import calendar
import logging
import traceback

from config import kite # Only kite object is needed from config now

# Configure logging for this module
logger = logging.getLogger(__name__) # Use the logger configured in app.py or monitor.py

def get_monthly_expiry(date_obj):
    """
    Calculates and returns the last Thursday of the given month as a datetime.date object.
    """
    year = date_obj.year
    month = date_obj.month
    
    # calendar.monthrange returns (weekday of first day, number of days in month)
    last_day = calendar.monthrange(year, month)[1]

    # Iterate backwards from the last day of the month to find the first Thursday
    for day in range(last_day, 0, -1):
        d = datetime.date(year, month, day)
        if d.weekday() == 3:  # Thursday is weekday 3 (Monday is 0, Sunday is 6)
            logger.debug(f"Resolved monthly expiry for {month}/{year}: {d}")
            return d
    
    # This case should ideally not be reached for valid months/years
    logger.error(f"Could not find a Thursday expiry for month {month}, year {year}.")
    return None

def get_sbin_symbols():
    """
    Fetches all SBIN future trading symbols from KiteConnect.
    Returns a sorted list of trading symbols (most recent first).
    """
    logger.info("Fetching all NFO instruments from KiteConnect...")
    try:
        instruments = kite.instruments("NFO")
        # Filter for SBIN futures and sort in reverse (latest expiry first)
        sbin_futures = sorted(
            [i["tradingsymbol"] for i in instruments if i["tradingsymbol"].startswith("SBIN") and i["instrument_type"] == "FUT"],
            reverse=True
        )
        logger.info(f"Found {len(sbin_futures)} SBIN FUT symbols.")
        return sbin_futures
    except Exception as e:
        logger.error(f"Error fetching SBIN symbols from Kite: {e}\n{traceback.format_exc()}")
        return []

def resolve_token(tradingsymbol):
    """
    Resolves the instrument token for a given trading symbol.
    This function assumes kite.instruments("NFO") has already been called
    and the instruments list is available or can be fetched.
    """
    try:
        instruments = kite.instruments("NFO") # Fetch instruments again or pass them in
        for inst in instruments:
            if inst["tradingsymbol"] == tradingsymbol:
                logger.debug(f"Resolved token for {tradingsymbol}: {inst['instrument_token']}")
                return inst["instrument_token"]
        logger.warning(f"Instrument token not found for trading symbol: {tradingsymbol}")
        return None
    except Exception as e:
        logger.error(f"Error resolving token for {tradingsymbol}: {e}\n{traceback.format_exc()}")
        return None


def resolve_sbin_future():
    """
    Determines the current SBIN future symbol to trade based on expiry and data availability.
    Handles rollover logic.
    Returns the resolved trading symbol string.
    Raises an Exception if no valid symbol is found.
    """
    today = datetime.date.today()
    expiry = get_monthly_expiry(today)

    if expiry is None:
        raise Exception("❌ Could not determine current month's expiry date.")

    # Rollover logic: Switch to next month's contract 2 days before current month's expiry
    # This ensures continuity and avoids trading near illiquid expiry.
    if (expiry - today).days <= 2:
        logger.info(f"Current expiry ({expiry}) is within 2 days. Rolling over to next month.")
        # Calculate next month: go to day 28 of current month, add 4 days to push to next month, then set day to 1
        next_month_date = (today.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        expiry = get_monthly_expiry(next_month_date)
        if expiry is None:
            raise Exception("❌ Could not determine next month's expiry date for rollover.")
        logger.info(f"Rolled over to new expiry: {expiry}")

    all_sbin = get_sbin_symbols()
    if not all_sbin:
        raise Exception("❌ No SBIN FUTURE symbols found from KiteConnect.")

    # Construct target symbol format (e.g., "SBIN24AUGFUT")
    # Year is last two digits, month is 3-letter uppercase abbreviation
    target_symbol_base = f"SBIN{str(expiry.year)[-2:]}{expiry.strftime('%b').upper()}FUT"
    logger.info(f"🔍 Trying to resolve SBIN future symbol for expiry: {expiry}")
    logger.info(f"🔧 Target Symbol Base: {target_symbol_base}")
    logger.debug(f"📦 All available SBIN FUT symbols (first 5): {all_sbin[:5]} ...")

    # Iterate through available symbols to find the one matching our target expiry
    for symbol in all_sbin:
        if target_symbol_base in symbol:
            logger.info(f"➡️ Attempting to validate symbol: {symbol}")
            try:
                # Resolve instrument token for historical data fetch
                token = resolve_token(symbol) # Uses the resolve_token defined in this file
                if token is None:
                    logger.warning(f"Could not get instrument token for {symbol}. Skipping.")
                    continue

                # Fetch historical data to ensure sufficient candles for analysis
                now_dt = datetime.datetime.now()
                # Fetch data for a slightly longer period to ensure 26 30-minute candles
                # 26 candles * 30 minutes = 780 minutes = 13 hours. Add buffer.
                past_dt = now_dt - datetime.timedelta(days=2) # Fetch last 2 days of data

                candles = kite.historical_data(
                    instrument_token=token,
                    from_date=past_dt,
                    to_date=now_dt,
                    interval="30minute"
                )
                logger.info(f"📈 {symbol} - Fetched {len(candles)} 30-minute candles.")

                # Check if enough candles are available for indicator calculation (e.g., 26 for MACD)
                if len(candles) >= 26:
                    logger.info(f"✅ Selected SBIN future: {symbol} (sufficient data: {len(candles)} candles)")
                    return symbol
                else:
                    logger.warning(f"⚠️ Insufficient data for {symbol}: only {len(candles)} candles found. Requires at least 26.")
            except Exception as e:
                logger.error(f"❌ Error fetching candles for {symbol}: {e}\n{traceback.format_exc()}")
                continue

    raise Exception("❌ No valid SBIN FUTURE symbol found with sufficient candle data for the target expiry.")

# Example usage (for local testing)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # --- Mock KiteConnect for standalone testing ---
    class MockKiteConnect:
        def instruments(self, exchange_type):
            logger.info(f"MockKiteConnect: Fetching instruments for {exchange_type}")
            return [
                {"tradingsymbol": "SBIN24JULFUT", "instrument_type": "FUT", "instrument_token": 1000},
                {"tradingsymbol": "SBIN24AUGFUT", "instrument_type": "FUT", "instrument_token": 1001},
                {"tradingsymbol": "SBIN24SEPFUT", "instrument_type": "FUT", "instrument_token": 1002},
                {"tradingsymbol": "NIFTY24AUGFUT", "instrument_type": "FUT", "instrument_token": 2000},
            ]

        def historical_data(self, instrument_token, from_date, to_date, interval):
            logger.info(f"MockKiteConnect: Fetching historical data for token {instrument_token} from {from_date} to {to_date} with {interval} interval.")
            if instrument_token == 1001:
                return [{"date": "...", "open": 100, "high": 105, "low": 98, "close": 102} for _ in range(30)]
            elif instrument_token == 1000:
                 return [{"date": "...", "open": 100, "high": 105, "low": 98, "close": 102} for _ in range(10)]
            return []

    # Override the imported kite with our mock for testing
    from config import kite as original_kite
    kite = MockKiteConnect()

    logger.info("--- Testing Symbol Resolver Module ---")

    try:
        resolved_symbol = resolve_sbin_future()
        logger.info(f"Final Resolved Symbol: {resolved_symbol}")
    except Exception as e:
        logger.error(f"Failed to resolve SBIN future: {e}")
