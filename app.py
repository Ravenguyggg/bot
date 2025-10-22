from flask import Flask
import os
from waitress import serve
import logging

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

@app.route('/')
def home():
    return "Discord Bot is running!"

@app.route('/health')
def health():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    logging.info(f"Starting web server on port {port}")
    serve(app, host='0.0.0.0', port=port)
