from flask import Flask, request, jsonify
from config import kite, current_position, WEBHOOK_SECRET
from symbol_resolver import resolve_sbin_future
from histogram import fetch_histogram
from order_manager import place_order
from monitor import start_monitor
from position_manager import fetch_existing_position

app = Flask(__name__)
start_monitor()

# On startup: check for existing position
if fetch_existing_position():
    print("✅ Existing SBIN position found. Monitoring for exit...")
else:
    print("🔍 No open position found. Waiting for TradingView signal to enter trade.")

@app.route("/", methods=["GET"])
def home():
    return "✅ SBIN Trading Bot is Live!"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📩 Webhook received:", data)

        # Verify secret key
        if data.get("secret") != WEBHOOK_SECRET:
            print("❌ Invalid secret key!")
            return jsonify({"status": "unauthorized"}), 403

        direction = data.get("direction", "").upper()
        price = float(data.get("price", 0))

        # Test signal to verify connectivity
        if direction == "TEST":
            print("🧪 Test webhook received successfully.")
            return jsonify({"status": "ok", "message": "Test successful"}), 200

        # Proceed only if LONG/SHORT
        if direction not in ["LONG", "SHORT"]:
            print("⚠️ Unknown direction:", direction)
            return jsonify({"status": "ignored", "reason": "Invalid direction"}), 400

        symbol = resolve_sbin_future()
        hist, prev_hist = fetch_histogram(symbol)[2:]

        # Confirm flip condition
        if direction == "LONG" and not (hist > 0 and prev_hist <= 0):
            return jsonify({"status": "ignored", "reason": "No green flip"})
        if direction == "SHORT" and not (hist < 0 and prev_hist >= 0):
            return jsonify({"status": "ignored", "reason": "No red flip"})

        order_id = place_order(symbol, direction, price)
        print(f"✅ Order placed: {order_id}")
        return jsonify({"status": "success", "order_id": order_id})

    except Exception as e:
        print("❌ Webhook error:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
