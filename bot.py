import discord
from discord.ext import commands
from discord import app_commands
import datetime
import logging
import sys
import os
from dotenv import load_dotenv
import asyncio
import json

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

# Store message logs and authorized data
message_logs = {}
authorized_data = {}

def load_authorized_data():
    """Load authorized users and roles from file"""
    global authorized_data
    try:
        with open('authorized.json', 'r') as f:
            authorized_data = json.load(f)
        logging.info("✅ Loaded authorized data from file")
    except FileNotFoundError:
        authorized_data = {}
        logging.info("ℹ️ No authorized data file found, starting fresh")
        save_authorized_data()

def save_authorized_data():
    """Save authorized users and roles to file"""
    try:
        with open('authorized.json', 'w') as f:
            json.dump(authorized_data, f, indent=2)
        logging.info("💾 Saved authorized data to file")
    except Exception as e:
        logging.error(f"❌ Failed to save authorized data: {e}")

def get_guild_data(guild_id):
    """Get or create guild data"""
    guild_id = str(guild_id)
    if guild_id not in authorized_data:
        authorized_data[guild_id] = {
            'users': [],
            'roles': []
        }
    return authorized_data[guild_id]

def is_authorized(interaction: discord.Interaction):
    """Check if user is authorized to use commands"""
    guild_data = get_guild_data(interaction.guild_id)
    
    # Check if user ID is in authorized users
    if str(interaction.user.id) in guild_data['users']:
        return True
    
    # Check if user has any authorized roles
    user_role_ids = [str(role.id) for role in interaction.user.roles]
    if any(role_id in guild_data['roles'] for role_id in user_role_ids):
        return True
    
    # Allow server administrators as fallback
    if interaction.user.guild_permissions.administrator:
        return True
    
    return False

@bot.event
async def on_ready():
    logging.info(f"Bot is ready! Logged in as {bot.user}")
    logging.info(f"Connected to {len(bot.guilds)} guilds:")
    
    for guild in bot.guilds:
        logging.info(f" - {guild.name} (ID: {guild.id})")
    
    # Load authorized data
    load_authorized_data()
    
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
    async def time(interaction: discord.Interaction):
        """Get current time"""
        if not is_authorized(interaction):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
            
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await interaction.response.send_message(
            f"{current_time}",
            ephemeral=True
        )

    @bot.tree.command(name="user", description="Get user info")
    async def user(interaction: discord.Interaction):
        """Get user info"""
        if not is_authorized(interaction):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
            
        await interaction.response.send_message(
            f"User: {interaction.user.display_name}\n"
            f"ID: {interaction.user.id}\n"
            f"Joined: {interaction.user.joined_at}",
            ephemeral=True
        )

    @bot.tree.command(name="logs", description="View message logs for specific channel")
    @app_commands.describe(channel="The channel to view logs from (optional)")
    async def logs(interaction: discord.Interaction, channel: discord.TextChannel = None):
        """View message logs for specific channel"""
        if not is_authorized(interaction):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
            
        if channel is None:
            channel = interaction.channel
        
        # Debug info
        logging.info(f"Checking logs for channel {channel.name} (ID: {channel.id})")
        logging.info(f"Available logged channels: {list(message_logs.keys())}")
        
        if channel.id not in message_logs or not message_logs[channel.id]:
            await interaction.response.send_message(
                f"No messages logged for {channel.mention}!\n"
                f"Use `/start_logging` first to begin logging this channel.",
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
    async def start_logging(interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Start logging messages in a channel"""
        if not is_authorized(interaction):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
            
        if channel is None:
            channel = interaction.channel
        
        if channel.id not in message_logs:
            message_logs[channel.id] = []
            await interaction.response.send_message(
                f"✅ Started logging messages in {channel.mention}!\n"
                f"Now monitoring all messages in this channel.",
                ephemeral=True
            )
            logging.info(f"Started logging channel: {channel.name} (ID: {channel.id})")
        else:
            await interaction.response.send_message(
                f"ℹ️ Already logging messages in {channel.mention}",
                ephemeral=True
            )

    @bot.tree.command(name="stop_logging", description="Stop logging messages in a channel")
    @app_commands.describe(channel="The channel to stop logging (optional)")
    async def stop_logging(interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Stop logging messages in a channel"""
        if not is_authorized(interaction):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
            
        if channel is None:
            channel = interaction.channel
        
        if channel.id in message_logs:
            message_count = len(message_logs[channel.id])
            del message_logs[channel.id]
            await interaction.response.send_message(
                f"✅ Stopped logging messages in {channel.mention}\n"
                f"Removed {message_count} logged messages.",
                ephemeral=True
            )
            logging.info(f"Stopped logging channel: {channel.name} (ID: {channel.id})")
        else:
            await interaction.response.send_message(
                f"ℹ️ Not currently logging messages in {channel.mention}",
                ephemeral=True
            )

    @bot.tree.command(name="logging_status", description="Check which channels are being logged")
    async def logging_status(interaction: discord.Interaction):
        """Check logging status for all channels"""
        if not is_authorized(interaction):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
        
        if not message_logs:
            await interaction.response.send_message(
                "No channels are currently being logged.\n"
                "Use `/start_logging` in a channel to begin.",
                ephemeral=True
            )
            return
        
        status_text = "**Currently Logging Channels:**\n\n"
        for channel_id, logs in message_logs.items():
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                status_text += f"📝 {channel.mention} - {len(logs)} messages logged\n"
            else:
                status_text += f"❓ Unknown Channel (ID: {channel_id}) - {len(logs)} messages\n"
        
        await interaction.response.send_message(status_text, ephemeral=True)

    # Authorization management commands
    @bot.tree.command(name="add_user", description="Add a user to authorized users")
    @app_commands.describe(user="The user to authorize")
    async def add_user(interaction: discord.Interaction, user: discord.User):
        """Add a user to authorized users"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command!", ephemeral=True)
            return
            
        guild_data = get_guild_data(interaction.guild_id)
        user_id = str(user.id)
        
        if user_id not in guild_data['users']:
            guild_data['users'].append(user_id)
            save_authorized_data()
            await interaction.response.send_message(
                f"✅ Added {user.mention} to authorized users!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ {user.mention} is already authorized!",
                ephemeral=True
            )

    @bot.tree.command(name="remove_user", description="Remove a user from authorized users")
    @app_commands.describe(user="The user to remove")
    async def remove_user(interaction: discord.Interaction, user: discord.User):
        """Remove a user from authorized users"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command!", ephemeral=True)
            return
            
        guild_data = get_guild_data(interaction.guild_id)
        user_id = str(user.id)
        
        if user_id in guild_data['users']:
            guild_data['users'].remove(user_id)
            save_authorized_data()
            await interaction.response.send_message(
                f"✅ Removed {user.mention} from authorized users!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ {user.mention} is not in authorized users!",
                ephemeral=True
            )

    @bot.tree.command(name="add_role", description="Add a role to authorized roles")
    @app_commands.describe(role="The role to authorize")
    async def add_role(interaction: discord.Interaction, role: discord.Role):
        """Add a role to authorized roles"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command!", ephemeral=True)
            return
            
        guild_data = get_guild_data(interaction.guild_id)
        role_id = str(role.id)
        
        if role_id not in guild_data['roles']:
            guild_data['roles'].append(role_id)
            save_authorized_data()
            await interaction.response.send_message(
                f"✅ Added {role.mention} to authorized roles!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ {role.mention} is already authorized!",
                ephemeral=True
            )

    @bot.tree.command(name="remove_role", description="Remove a role from authorized roles")
    @app_commands.describe(role="The role to remove")
    async def remove_role(interaction: discord.Interaction, role: discord.Role):
        """Remove a role from authorized roles"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command!", ephemeral=True)
            return
            
        guild_data = get_guild_data(interaction.guild_id)
        role_id = str(role.id)
        
        if role_id in guild_data['roles']:
            guild_data['roles'].remove(role_id)
            save_authorized_data()
            await interaction.response.send_message(
                f"✅ Removed {role.mention} from authorized roles!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ {role.mention} is not in authorized roles!",
                ephemeral=True
            )

    @bot.tree.command(name="list_authorized", description="Show all authorized users and roles")
    async def list_authorized(interaction: discord.Interaction):
        """Show all authorized users and roles"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command!", ephemeral=True)
            return
            
        guild_data = get_guild_data(interaction.guild_id)
        
        embed = discord.Embed(title="Authorized Users & Roles", color=0x00ff00)
        
        # Show authorized users
        if guild_data['users']:
            users_text = ""
            for user_id in guild_data['users']:
                user_obj = interaction.guild.get_member(int(user_id))
                if user_obj:
                    users_text += f"{user_obj.mention} (`{user_id}`)\n"
                else:
                    users_text += f"Unknown User (`{user_id}`)\n"
            embed.add_field(name="👥 Authorized Users", value=users_text or "None", inline=False)
        else:
            embed.add_field(name="👥 Authorized Users", value="None", inline=False)
        
        # Show authorized roles
        if guild_data['roles']:
            roles_text = ""
            for role_id in guild_data['roles']:
                role_obj = interaction.guild.get_role(int(role_id))
                if role_obj:
                    roles_text += f"{role_obj.mention} (`{role_id}`)\n"
                else:
                    roles_text += f"Unknown Role (`{role_id}`)\n"
            embed.add_field(name="🎭 Authorized Roles", value=roles_text or "None", inline=False)
        else:
            embed.add_field(name="🎭 Authorized Roles", value="None", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="sync", description="Manual command sync (admin only)")
    async def sync(interaction: discord.Interaction):
        """Manual command sync"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need administrator permissions to use this command!", ephemeral=True)
            return
            
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
        # Keep only last 100 messages per channel
        if len(message_logs[message.channel.id]) > 100:
            message_logs[message.channel.id].pop(0)
        
        logging.info(f"[{message.channel.name}] [{log_entry['timestamp']}] {log_entry['author']}: {log_entry['content']}")
    
    await bot.process_commands(message)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    logging.error(f"Command error: {error}")
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
