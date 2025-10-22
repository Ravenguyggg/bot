import discord
from discord.ext import commands
from discord import app_commands
import datetime
import logging
import sys
import os
from dotenv import load_dotenv
import asyncio
from flask import Flask
from threading import Thread

# Load .env file if it exists
load_dotenv()

# Simple Flask app for health checks
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

@app.route('/health')
def health():
    return "OK"

def run_web():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# Your existing bot code continues here...
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# ... rest of your bot code remains exactly the same ...

async def main():
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        raise ValueError("No Discord token found!")
    
    try:
        await bot.start(TOKEN)
    except Exception as e:
        logging.error(f"Error starting bot: {e}")

if __name__ == "__main__":
    # Start web server in background if PORT is set (Render)
    if os.environ.get('PORT'):
        web_thread = Thread(target=run_web, daemon=True)
        web_thread.start()
        print("Web server started for health checks")
    
    # Run bot
    asyncio.run(main())
