import datetime
import pandas as pd
import logging
import traceback

# Import kite object from config
from config import kite
# Import resolve_token from symbol_resolver (where it was moved)
from symbol_resolver import resolve_sbin_future, resolve_token

# Configure logging for this module
logger = logging.getLogger(__name__) # Use the logger configured in app.py or monitor.py

# ========== Get Candles ==========

def get_candles(symbol, days_back=7):
    """
    Fetches historical 30-minute candles for a given symbol from KiteConnect.
    """
    try:
        to_date = datetime.datetime.now()
        from_date = to_date - datetime.timedelta(days=days_back)
        
        # Resolve instrument token using the function from symbol_resolver
        instrument_token = resolve_token(symbol)
        if instrument_token is None:
            logger.error(f"❌ Could not resolve instrument token for {symbol}. Cannot fetch candles.")
            return []

        logger.info(f"Fetching historical data for {symbol} (token: {instrument_token}) from {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}...")
        candles = kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date,
            to_date=to_date,
            interval="30minute" # Hardcoded interval, consider making configurable if needed
        )
        logger.info(f"📊 Got {len(candles)} candles for {symbol}")
        return candles
    except Exception as e:
        logger.error(f"❌ Error fetching candles for {symbol}: {e}\n{traceback.format_exc()}")
        return []

# ========== Fetch Histogram ==========

def fetch_histogram(symbol=None, days_back=7):
    """
    Calculates the MACD histogram and detects crossover signals for a given symbol.
    If no symbol is provided, it resolves the SBIN future symbol.
    Returns a dictionary with histogram data and crossover flags, and a status string.
    """
    try:
        if symbol is None:
            # Resolve the symbol if not provided (e.g., for initial entry signal)
            resolved_symbol = resolve_sbin_future()
            if resolved_symbol is None:
                logger.error("❌ Failed to resolve SBIN future symbol for histogram calculation.")
                return None, "error_symbol_resolution"
            used_symbol = resolved_symbol
        else:
            used_symbol = symbol

        candles = get_candles(used_symbol, days_back)

        if not candles:
            logger.warning(f"⚠️ No candles fetched for {used_symbol}. Cannot calculate histogram.")
            return None, "error_no_candles"

        # MACD typically uses 26 periods for EMA, so ensure enough data
        if len(candles) < 26: # Hardcoded minimum candles, consider making configurable
            logger.warning(f"⚠️ Not enough candles ({len(candles)}) for {used_symbol}. Requires at least 26 for MACD calculation.")
            return None, "error_insufficient_data"

        df = pd.DataFrame(candles)
        df.columns = ["date", "open", "high", "low", "close", "volume"]
        
        # Ensure 'close' column is numeric
        df['close'] = pd.to_numeric(df['close'])

        # MACD Calculation (12-period EMA, 26-period EMA, 9-period Signal Line)
        df['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = df['ema12'] - df['ema26']
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['hist'] = df['macd'] - df['signal']

        # Get the latest and previous histogram values
        # Ensure there are at least two rows for comparison
        if len(df) < 2:
            logger.warning(f"⚠️ Not enough data points to determine histogram cross. Only {len(df)} rows.")
            return None, "error_insufficient_history"

        latest_hist = df['hist'].iloc[-1]
        prev_hist = df['hist'].iloc[-2]

        # Determine crossover conditions
        cross_to_green = latest_hist > 0 and prev_hist <= 0
        cross_to_red = latest_hist < 0 and prev_hist >= 0

        logger.info(f"📊 Histogram for {used_symbol}: Latest={latest_hist:.4f}, Prev={prev_hist:.4f}")
        logger.info(f"  Cross to Green: {cross_to_green} | Cross to Red: {cross_to_red}")

        return {
            "hist": latest_hist,
            "cross_to_green": cross_to_green,
            "cross_to_red": cross_to_red,
            "used_symbol": used_symbol
        }, "ok"

    except Exception as e:
        logger.error(f"❌ Critical error in MACD histogram calculation for {symbol}: {e}\n{traceback.format_exc()}")
        return None, "error_calculation_failed"

# Example usage (for local testing)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # --- Mock KiteConnect for standalone testing ---
    # In a real scenario, 'kite' would be a properly initialized KiteConnect object.
    # For testing this module in isolation, we'll create a mock.
    class MockKiteConnect:
        def instruments(self, exchange_type):
            return [
                {"tradingsymbol": "SBIN24AUGFUT", "instrument_type": "FUT", "instrument_token": 1001},
            ]
        def historical_data(self, instrument_token, from_date, to_date, interval):
            if instrument_token == 1001:
                # Simulate enough candles for MACD (e.g., 30 candles)
                # Generate some dummy price data that could show a cross
                data = []
                base_price = 500.0
                for i in range(30):
                    close_price = base_price + (i * 0.5) + (5 * (i % 5 - 2)) # Simulate some fluctuation
                    data.append({
                        "date": datetime.datetime.now() - datetime.timedelta(minutes=(30-i)*30),
                        "open": close_price - 1, "high": close_price + 1, "low": close_price - 2,
                        "close": close_price, "volume": 1000
                    })
                # Force a cross for testing
                if len(data) >= 2:
                    data[-2]["close"] = 510 # Adjust prev close
                    data[-1]["close"] = 505 # Adjust latest close
                return data
            return []

    # Override the imported kite with our mock for testing
    from config import kite as original_kite_obj
    kite = MockKiteConnect()

    # Override resolve_token for testing
    from symbol_resolver import resolve_token as original_resolve_token_func
    def mock_resolve_token(symbol):
        if symbol == "SBIN24AUGFUT":
            return 1001
        return None
    resolve_token = mock_resolve_token


    logger.info("--- Testing Histogram Module ---")

    try:
        # Test with a specific symbol
        hist_data, status = fetch_histogram(symbol="SBIN24AUGFUT")
        logger.info(f"Result for SBIN24AUGFUT: {hist_data}, Status: {status}")

        # Test without a symbol (should resolve automatically)
        hist_data_auto, status_auto = fetch_histogram()
        logger.info(f"Result (auto-resolved): {hist_data_auto}, Status: {status_auto}")

        # Test with insufficient data
        # Temporarily mock get_candles to return less data
        original_get_candles = get_candles
        def mock_get_candles_insufficient(symbol, days_back):
            return [{"date": "...", "close": 100} for _ in range(10)] # Only 10 candles
        get_candles = mock_get_candles_insufficient
        
        logger.info("\n--- Testing with Insufficient Data ---")
        hist_data_insufficient, status_insufficient = fetch_histogram(symbol="DUMMYFUT")
        logger.info(f"Result (insufficient data): {hist_data_insufficient}, Status: {status_insufficient}")
        
        # Restore original get_candles
        get_candles = original_get_candles

    except Exception as e:
        logger.error(f"Test failed: {e}")

    # Restore original kite object and resolve_token function if running in a larger application context
    # kite = original_kite_obj
    # resolve_token = original_resolve_token_func
