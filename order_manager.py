import logging
import datetime
from kiteconnect import KiteConnect

# Import project-specific configuration
import config
# Assuming your `indicator.py` file has a function to fetch indicator values
from indicator import get_latest_indicators
from symbol_resolver import SymbolResolver

# Configure logging for this module
logger = logging.getLogger(__name__)

class OrderManager:
    """
    Manages order placement based on a combination of EMA crossover and ADX.

    This class fetches indicator values from the `indicator.py` file and then
    places orders according to a predefined strategy.
    
    Strategy:
    - BUY: EMA(9) crosses above EMA(21) AND ADX >= 20
    - SELL: EMA(9) crosses below EMA(21) AND ADX >= 20
    """

    def __init__(self, kite_client: KiteConnect):
        """
        Initializes the OrderManager with a KiteConnect client.
        
        Args:
            kite_client (KiteConnect): An authenticated KiteConnect client instance.
        """
        self.kite = kite_client
        # Instantiate SymbolResolver with the kite client
        self.symbol_resolver = SymbolResolver(kite_client)
        logger.info("OrderManager initialized.")

    def check_and_place_order(self):
        """
        Checks for trading conditions and places an order if a signal is generated.
        
        This method automatically uses the instrument and other parameters from config.py.
        """
        try:
            # 1. Get the current trading symbol and instrument token
            trading_symbol = self.symbol_resolver.resolve_current_month_symbol()
            instrument_token = self.symbol_resolver.resolve_token(trading_symbol)

            if not instrument_token:
                logger.error(f"Could not resolve instrument token for {trading_symbol}. Aborting.")
                return

            # 2. Fetch historical data to pass to the indicator module
            # We need to fetch enough data for the indicators to be calculated
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=60)
            
            historical_data = self.kite.historical_data(instrument_token, start_date, end_date, 'day')
            
            if not historical_data:
                logger.warning("No historical data found. Cannot place order.")
                return

            # 3. Get latest indicator values from the `indicator.py` module
            # Assumes `get_latest_indicators` returns a tuple of (last_ema9, prev_ema9, last_ema21, prev_ema21, last_adx)
            last_ema9, prev_ema9, last_ema21, prev_ema21, last_adx = get_latest_indicators(historical_data)

            logger.info(f"Checking conditions for {trading_symbol}...")
            logger.info(f"Last EMA9: {last_ema9:.2f}, Prev EMA9: {prev_ema9:.2f}")
            logger.info(f"Last EMA21: {last_ema21:.2f}, Prev EMA21: {prev_ema21:.2f}")
            logger.info(f"Last ADX: {last_adx:.2f}")

            # 4. Check for a buy signal
            # EMA(9) crosses above EMA(21) AND ADX is strong
            if (prev_ema9 <= prev_ema21 and last_ema9 > last_ema21) and (last_adx >= 20):
                logger.info("BUY signal detected! Placing a market order...")
                # Place a buy order
                try:
                    order_id = self.kite.place_order(
                        tradingsymbol=trading_symbol,
                        exchange=self.kite.EXCHANGE_NFO,
                        transaction_type=self.kite.TRANSACTION_TYPE_BUY,
                        quantity=config.lotsize,
                        product=config.product,
                        order_type=self.kite.ORDER_TYPE_MARKET,
                        variety=config.variety,
                    )
                    logger.info(f"Buy order placed successfully. Order ID: {order_id}")
                except Exception as e:
                    logger.error(f"Failed to place buy order: {e}", exc_info=True)

            # 5. Check for a sell signal
            # EMA(9) crosses below EMA(21) AND ADX is strong
            elif (prev_ema9 >= prev_ema21 and last_ema9 < last_ema21) and (last_adx >= 20):
                logger.info("SELL signal detected! Placing a market order...")
                # Place a sell order
                try:
                    order_id = self.kite.place_order(
                        tradingsymbol=trading_symbol,
                        exchange=self.kite.EXCHANGE_NFO,
                        transaction_type=self.kite.TRANSACTION_TYPE_SELL,
                        quantity=config.lotsize,
                        product=config.product,
                        order_type=self.kite.ORDER_TYPE_MARKET,
                        variety=config.variety,
                    )
                    logger.info(f"Sell order placed successfully. Order ID: {order_id}")
                except Exception as e:
                    logger.error(f"Failed to place sell order: {e}", exc_info=True)
            
            else:
                logger.info("No trading signal detected based on the strategy.")

        except Exception as e:
            logger.error(f"An error occurred during order processing: {e}", exc_info=True)
