# shared_state.py
import threading

# Event to signal graceful shutdown across threads
shutdown_requested = threading.Event()
