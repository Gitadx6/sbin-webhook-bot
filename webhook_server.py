from flask import Flask, request, jsonify
from kiteconnect import KiteConnect
import os

app = Flask(__name__)

API_KEY = os.getenv("KITE_API_KEY")
ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("🔔 Webhook received:", data)

    if data.get("secret") != WEBHOOK_SECRET:
        return jsonify({"status": "unauthorized"}), 403

    try:
        order_id = kite.place_order(
            tradingsymbol=data["instrument"],
            exchange=data.get("exchange", "NFO"),
            transaction_type=data["action"],
            quantity=int(data["quantity"]),
            order_type="MARKET",
            product=data.get("product", "NRML"),
            variety="regular"
        )
        print(f"✅ Order placed: {order_id}")
        return jsonify({"status": "success", "order_id": order_id})
    except Exception as e:
        print("❌ Error:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/", methods=["GET"])
def home():
    return "🚀 SBIN Webhook Bot is Running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
