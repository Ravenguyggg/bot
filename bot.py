import discord
from discord.ext import commands
from discord import app_commands
import datetime
import logging
import sys
import os
from dotenv import load_dotenv
import asyncio

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
TEST_GUILD_ID = 1087033723347808317
SECOND_GUILD_ID = 1342381217672200274
TEST_GUILD = discord.Object(id=TEST_GUILD_ID)
SECOND_GUILD = discord.Object(id=SECOND_GUILD_ID)

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
    logging.info(f"Connected to {len(bot.guilds)} guilds:")
    
    for guild in bot.guilds:
        logging.info(f" - {guild.name} (ID: {guild.id})")
        # Check if bot has permissions in this guild
        permissions = guild.get_member(bot.user.id).guild_permissions
        if not permissions.manage_guild:
            logging.warning(f"Bot missing 'Manage Guild' permission in {guild.name}")
        if not permissions.administrator:
            logging.warning(f"Bot missing 'Administrator' permission in {guild.name}")

    # Sync commands to specific guilds
    await sync_guild_commands(TEST_GUILD, "Test Guild")
    await sync_guild_commands(SECOND_GUILD, "Second Guild")

async def sync_guild_commands(guild, guild_name):
    """Sync commands to a specific guild"""
    try:
        # Copy global commands to guild
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        logging.info(f"✅ Successfully synced {len(synced)} commands to {guild_name}")
        return True
    except discord.Forbidden:
        logging.error(f"❌ Missing permissions to sync commands in {guild_name}. Bot needs 'applications.commands' scope and 'Manage Guild' permission.")
        return False
    except Exception as e:
        logging.error(f"❌ Failed to sync commands to {guild_name}: {e}")
        return False

def setup_commands():
    """Setup all commands for both guilds"""
    
    @bot.tree.command(name="time", description="Get current time")
    @app_commands.checks.has_any_role(*AUTHORIZED_ROLE_IDS)
    async def time(interaction: discord.Interaction):
        """Get current time"""
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await interaction.response.send_message(
            f"{current_time}",
            ephemeral=True
        )

    @bot.tree.command(name="user", description="Get user info")
    @app_commands.checks.has_any_role(*AUTHORIZED_ROLE_IDS)
    async def user(interaction: discord.Interaction):
        """Get user info"""
        await interaction.response.send_message(
            f"{interaction.user}",
            ephemeral=True
        )

    @bot.tree.command(name="logs", description="View message logs for specific channel")
    @app_commands.describe(channel="The channel to view logs from (optional)")
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

    @bot.tree.command(name="start_logging", description="Start logging messages in a channel")
    @app_commands.describe(channel="The channel to start logging (optional)")
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

    @bot.tree.command(name="stop_logging", description="Stop logging messages in a channel")
    @app_commands.describe(channel="The channel to stop logging (optional)")
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

    @bot.tree.command(name="sync", description="Manual command sync (admin only)")
    @app_commands.checks.has_any_role(*AUTHORIZED_ROLE_IDS)
    async def sync(interaction: discord.Interaction):
        """Manual command sync"""
        await interaction.response.defer(ephemeral=True)
        
        success_count = 0
        if await sync_guild_commands(TEST_GUILD, "Test Guild"):
            success_count += 1
        if await sync_guild_commands(SECOND_GUILD, "Second Guild"):
            success_count += 1
            
        await interaction.followup.send(
            f"Command sync completed! {success_count}/2 guilds synced successfully.",
            ephemeral=True
        )

# Setup all commands
setup_commands()

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

async def main():
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        raise ValueError("No Discord token found!")
    
    try:
        await bot.start(TOKEN)
    except Exception as e:
        logging.error(f"Error starting bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())
