from flask import Flask, request, jsonify
from config import kite, current_position, WEBHOOK_SECRET
from symbol_resolver import resolve_sbin_future
from histogram import fetch_histogram
from order_manager import place_order
from monitor import start_monitor
from position_manager import fetch_existing_position
from monitor import start_monitor

app = Flask(__name__)
start_monitor()

if fetch_existing_position():
    start_monitor()

@app.route("/", methods=["GET"])
def home():
    return "✅ SBIN Trading Bot is Live!"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        if data.get("secret") != WEBHOOK_SECRET:
            return jsonify({"status": "unauthorized"}), 403

        direction = data.get("direction", "").upper()
        price = float(data["price"])
        symbol = resolve_sbin_future()
        hist, prev_hist = fetch_histogram(symbol)[2:]

        if direction == "LONG" and not (hist > 0 and prev_hist <= 0):
            return jsonify({"status": "ignored", "reason": "No green flip"})
        if direction == "SHORT" and not (hist < 0 and prev_hist >= 0):
            return jsonify({"status": "ignored", "reason": "No red flip"})

        order_id = place_order(symbol, direction, price)
        return jsonify({"status": "success", "order_id": order_id})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
