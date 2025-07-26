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
    try:
        data = request.json
        print("🔔 Webhook received:", data, flush=True)

        if data.get("secret") != WEBHOOK_SECRET:
            print("❌ Invalid secret!", flush=True)
            return jsonify({"status": "unauthorized"}), 403

        order_id = kite.place_order(
            tradingsymbol=data["instrument"],  # 👈 If this key is missing, it will crash
            exchange=data.get("exchange", "NFO"),
            transaction_type=data["action"],
            quantity=int(data["quantity"]),
            order_type="MARKET",
            product=data.get("product", "NRML"),
            variety="regular"
        )

        print(f"✅ Order placed: {order_id}", flush=True)
        return jsonify({"status": "success", "order_id": order_id})

    except Exception as e:
        print("❌ Error placing order:", str(e), flush=True)
        return jsonify({"status": "error", "message": str(e)}), 500
@app.route("/", methods=["GET"])
def home():
    return "🚀 SBIN Webhook Bot is Running!"

@app.route("/test", methods=["POST"])//trade vewi testing
def test_alert():
    print("✅ Test alert received from TradingView:", request.json, flush=True)
    return jsonify({"status": "test success", "data": request.json})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
print("🚀 Deployed version 1.1")

