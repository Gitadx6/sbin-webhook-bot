import logging
import datetime
import pandas as pd
from kiteconnect import KiteConnect

class KiteClient:
    def __init__(self, kite: KiteConnect):
        """
        Initializes the KiteClient.
        :param kite: The initialized KiteConnect object.
        """
        self.kite = kite
        self.logger = logging.getLogger(__name__)

    def get_historical_data(self, instrument_token: int, interval: str, from_date: datetime, to_date: datetime) -> pd.DataFrame:
        """
        Fetches historical data from the KiteConnect API.
        :return: A Pandas DataFrame with historical OHLCV data.
        """
        if not self.kite:
            self.logger.error("KiteConnect object is not initialized. Cannot fetch historical data.")
            return pd.DataFrame()
        
        self.logger.info(f"Fetching historical data for {instrument_token} from {from_date} to {to_date}...")
        try:
            raw_data = self.kite.historical_data(instrument_token, from_date, to_date, interval)
            df = pd.DataFrame(raw_data)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            return df
        except Exception as e:
            self.logger.error(f"Error fetching historical data: {e}", exc_info=True)
            return pd.DataFrame()

    def get_live_data(self, instrument_token: int, interval: str) -> dict:
        """
        Fetches the latest completed candle from the KiteConnect API.
        This function fetches a small window of data and returns the last available candle,
        assuming it is a completed candle.
        :return: A dictionary representing the latest completed candle, or None if no data is found.
        """
        if not self.kite:
            self.logger.error("KiteConnect object is not initialized. Cannot fetch live data.")
            return None
        
        # It's better to fetch a short window to ensure we get the latest completed candle.
        # KiteConnect's historical data API returns only completed candles.
        to_date = datetime.datetime.now()
        # Fetch data for the last hour to be safe and ensure a completed candle is available.
        from_date = to_date - datetime.timedelta(hours=1) 
        
        self.logger.info("Fetching latest candle from Kite...")
        try:
            raw_data = self.kite.historical_data(instrument_token, from_date, to_date, interval, continuous=False)
            
            # If the API returns any data, get the last candle.
            if raw_data:
                # Convert the last dictionary in the list to a DataFrame
                df = pd.DataFrame([raw_data[-1]])
                # Convert the date column to datetime objects
                df['date'] = pd.to_datetime(df['date'])
                
                # Check if the candle is not a duplicate of a previously fetched candle.
                # The main bot logic will handle this check, but it is a good practice
                # to check it here too if necessary.
                
                # Convert the DataFrame row back to a dictionary and return it.
                return df.iloc[0].to_dict()
            else:
                return None
        except Exception as e:
            self.logger.error(f"Error fetching live data: {e}", exc_info=True)
            return None

    def place_order(self, instrument_token: int, transaction_type: str, quantity: int):
        """
        Places a live order via the KiteConnect API.
        :param transaction_type: 'BUY' or 'SELL'.
        """
        if not self.kite:
            self.logger.error("KiteConnect object is not initialized. Cannot place order.")
            return

        self.logger.info(f"Placing a {transaction_type} order for {quantity} units of {instrument_token}")
        try:
            # This is a sample order placement. You may need to customize this.
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=self.kite.EXCHANGE_NSE,
                tradingsymbol=config.Instrument,
                transaction_type=self.kite.TRANSACTION_TYPE_BUY if transaction_type == 'BUY' else self.kite.TRANSACTION_TYPE_SELL,
                quantity=quantity,
                product=self.kite.PRODUCT_MIS,
                order_type=self.kite.ORDER_TYPE_MARKET
            )
            self.logger.info(f"Order placed successfully. Order ID: {order_id}")
            return order_id
        except Exception as e:
            self.logger.error(f"Error placing order: {e}", exc_info=True)
            return None
