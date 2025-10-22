import discord
from discord.ext import commands
from discord import app_commands
import datetime
import logging
import sys
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

TEST_GUILD = discord.Object(id=1087033723347808317)
SECOND_GUILD = discord.Object(id=1342381217672200274)

AUTHORIZED_ROLE_IDS = [
    1425745494654849024,  # admin 17 pro max
    1426211908603871232,  # admin 17
    1429395961352032266,  # i can ban you
    765477017646530560    # me
]

message_logs = {}

@bot.event
async def on_ready():
    logging.info(f"Bot is ready! Logged in as {bot.user}")
    try:
        await bot.tree.sync()
        synced1 = await bot.tree.sync(guild=TEST_GUILD)
        synced2 = await bot.tree.sync(guild=SECOND_GUILD)
        logging.info(f"Synced {len(synced1)} commands to test guild")
        logging.info(f"Synced {len(synced2)} commands to second guild")
    except Exception as e:
        logging.error(f"Failed to sync commands: {e}")

def multi_guild_command():
    def decorator(func):
        bot.tree.command(guild=TEST_GUILD)(func)
        bot.tree.command(guild=SECOND_GUILD)(func)
        return func
    return decorator

@multi_guild_command()
@app_commands.checks.has_any_role(*AUTHORIZED_ROLE_IDS)
async def time(interaction: discord.Interaction):
    """Get current time"""
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response = f"Current Date and Time (UTC - YYYY-MM-DD HH:MM:SS formatted): {current_time}\nCurrent User's Login: {interaction.user}\n"
    await interaction.response.send_message(response, ephemeral=True)

@multi_guild_command()
@app_commands.checks.has_any_role(*AUTHORIZED_ROLE_IDS)
async def user(interaction: discord.Interaction):
    """Get user info"""
    response = f"Current Date and Time (UTC - YYYY-MM-DD HH:MM:SS formatted): {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nCurrent User's Login: {interaction.user}\n"
    await interaction.response.send_message(response, ephemeral=True)

# [Rest of your commands stay the same...]

if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        raise ValueError("No Discord token found!")
    
    try:
        bot.run(TOKEN)
    except Exception as e:
        logging.error(f"Error starting bot: {e}")
