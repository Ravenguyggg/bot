import discord
from discord.ext import commands
from discord import app_commands
import datetime
import logging
import sys
import os
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# Both servers
TEST_GUILD = discord.Object(id=1087033723347808317)
SECOND_GUILD = discord.Object(id=1342381217672200274)

# Predefined roles
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
    await interaction.response.send_message(
        f"Current Date and Time (UTC - YYYY-MM-DD HH:MM:SS formatted): {current_time}",
        ephemeral=True
    )

@multi_guild_command()
@app_commands.checks.has_any_role(*AUTHORIZED_ROLE_IDS)
async def user(interaction: discord.Interaction):
    """Get user info"""
    await interaction.response.send_message(
        f"Current User's Login: {interaction.user}",
        ephemeral=True
    )

@multi_guild_command()
@app_commands.checks.has_any_role(*AUTHORIZED_ROLE_IDS)
async def logs(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """View message logs for specific channel"""
    if channel is None:
        channel = interaction.channel
    
    if channel.id not in message_logs or not message_logs[channel.id]:
        await interaction.response.send_message(
            f"No messages logged for {channel.mention}!", 
            ephemeral=True
        )
        return
    
    log_text = f"**Recent Messages in {channel.mention}:**\n\n"
    for log in reversed(message_logs[channel.id][-10:]):
        log_text += f"**{log['author']}** at {log['timestamp']}\n"
        log_text += f"{log['content']}\n\n"
    
    await interaction.response.send_message(log_text, ephemeral=True)

@multi_guild_command()
@app_commands.checks.has_any_role(*AUTHORIZED_ROLE_IDS)
async def start_logging(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Start logging messages in a channel"""
    if channel is None:
        channel = interaction.channel
    
    if channel.id not in message_logs:
        message_logs[channel.id] = []
        await interaction.response.send_message(
            f"Started logging messages in {channel.mention}",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"Already logging messages in {channel.mention}",
            ephemeral=True
        )

@multi_guild_command()
@app_commands.checks.has_any_role(*AUTHORIZED_ROLE_IDS)
async def stop_logging(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Stop logging messages in a channel"""
    if channel is None:
        channel = interaction.channel
    
    if channel.id in message_logs:
        del message_logs[channel.id]
        await interaction.response.send_message(
            f"Stopped logging messages in {channel.mention}",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"Not logging messages in {channel.mention}",
            ephemeral=True
        )

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Only log if channel is being monitored
    if message.channel.id in message_logs:
        log_entry = {
            'author': str(message.author),
            'content': message.content,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        message_logs[message.channel.id].append(log_entry)
        if len(message_logs[message.channel.id]) > 100:
            message_logs[message.channel.id].pop(0)
        
        print(f"[{message.channel.name}] [{log_entry['timestamp']}] {log_entry['author']}: {log_entry['content']}")
    
    await bot.process_commands(message)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingAnyRole):
        await interaction.response.send_message(
            "You don't have permission to use this command!",
            ephemeral=True
        )
    else:
        logging.error(f"Error: {error}")
        await interaction.response.send_message(
            "Something went wrong!",
            ephemeral=True
        )

if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        raise ValueError("No Discord token found!")
    
    try:
        bot.run(TOKEN)
    except Exception as e:
        logging.error(f"Error starting bot: {e}")
