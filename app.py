from flask import Flask, request, jsonify
from config import kite, current_position, WEBHOOK_SECRET
from symbol_resolver import resolve_sbin_future
from histogram import fetch_histogram
from order_manager import place_order
from monitor import start_monitor
from position_manager import fetch_existing_position
import threading
import time

app = Flask(__name__)
start_monitor()

# Background thread to periodically check for existing positions
def auto_position_checker():
    while True:
        if not current_position["active"]:
            found = fetch_existing_position()
            if found:
                print("🔁 Position auto-detected. Monitoring for exit...", flush=True)
        time.sleep(60)  # Check every 60 seconds

threading.Thread(target=auto_position_checker, daemon=True).start()

# On startup: check for existing position
if fetch_existing_position():
    print("✅ Existing SBIN position found. Monitoring for exit...", flush=True)
else:
    print("🔍 No open position found. Waiting for TradingView signal to enter trade.", flush=True)

@app.route("/", methods=["GET"])
def home():
    return "✅ SBIN Trading Bot is Live!"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📩 Webhook received:", data, flush=True)

        # Verify secret key
        if data.get("secret") != WEBHOOK_SECRET:
            print("❌ Invalid secret key!", flush=True)
            return jsonify({"status": "unauthorized"}), 403

        direction = data.get("direction", "").upper()
        price = float(data.get("price", 0))

        # Test signal to verify connectivity
        if direction == "TEST":
            print("🧪 Test webhook received successfully.", flush=True)
            return jsonify({"status": "ok", "message": "Test successful"}), 200

        # Proceed only if LONG/SHORT
        if direction not in ["LONG", "SHORT"]:
            print("⚠️ Unknown direction:", direction, flush=True)
            return jsonify({"status": "ignored", "reason": "Invalid direction"}), 400

        symbol = resolve_sbin_future()

        # ✅ Safe fetch_histogram usage
        result, status = fetch_histogram(symbol)

        if status != "ok" or result is None:
            print(f"❌ Histogram fetch failed for {symbol}, skipping trade entry.", flush=True)
            return jsonify({"status": "error", "reason": "Histogram fetch failed"}), 500

        hist = result["hist"]
        cross_to_green = result["cross_to_green"]
        cross_to_red = result["cross_to_red"]

        # Confirm flip condition
        if direction == "LONG" and not (hist > 0 and cross_to_green):
            print("⛔ No green flip, ignoring LONG entry.", flush=True)
            return jsonify({"status": "ignored", "reason": "No green flip"})
        if direction == "SHORT" and not (hist < 0 and cross_to_red):
            print("⛔ No red flip, ignoring SHORT entry.", flush=True)
            return jsonify({"status": "ignored", "reason": "No red flip"})

        order_id = place_order(symbol, direction, price)
        print(f"✅ Order placed: {order_id}", flush=True)
        return jsonify({"status": "success", "order_id": order_id})

    except Exception as e:
        print("❌ Webhook error:", str(e), flush=True)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
