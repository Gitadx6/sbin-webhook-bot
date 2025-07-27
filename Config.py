from kiteconnect import KiteConnect
import os

API_KEY = os.getenv("KITE_API_KEY")
ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

# Global position tracker
current_position = {
    "symbol": None,
    "side": None,
    "entry_price": None,
    "stop_loss": None,
    "trailing_sl": None,
    "quantity": None,
    "active": False
}
