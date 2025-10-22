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
import threading

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

# Store message logs and authorized data
message_logs = {}
authorized_data = {}
auto_ban_config = {}

def load_data():
    """Load authorized users, roles, and auto-ban config from files"""
    global authorized_data, auto_ban_config
    
    # Load authorized data
    try:
        with open('authorized.json', 'r') as f:
            authorized_data = json.load(f)
        logging.info("✅ Loaded authorized data from file")
    except FileNotFoundError:
        authorized_data = {}
        logging.info("ℹ️ No authorized data file found, starting fresh")
        save_authorized_data()
    
    # Load auto-ban config
    try:
        with open('auto_ban_config.json', 'r') as f:
            auto_ban_config = json.load(f)
        logging.info("✅ Loaded auto-ban config from file")
    except FileNotFoundError:
        auto_ban_config = {
            'enabled': False,  # Disabled by default for safety
            'ban_message': "🚫 You have been automatically banned for posting prohibited content.",
            'log_channel': None,
            'banned_content': ['image', 'gif', 'video', 'file'],
            'exempt_roles': [],
            'exempt_channels': []
        }
        save_auto_ban_config()

def save_authorized_data():
    """Save authorized users and roles to file"""
    try:
        with open('authorized.json', 'w') as f:
            json.dump(authorized_data, f, indent=2)
    except Exception as e:
        logging.error(f"❌ Failed to save authorized data: {e}")

def save_auto_ban_config():
    """Save auto-ban configuration to file"""
    try:
        with open('auto_ban_config.json', 'w') as f:
            json.dump(auto_ban_config, f, indent=2)
    except Exception as e:
        logging.error(f"❌ Failed to save auto-ban config: {e}")

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
    # Allow everyone for now to test
    if interaction.user.guild_permissions.administrator:
        return True
    
    guild_data = get_guild_data(interaction.guild_id)
    
    # Check if user ID is in authorized users
    if str(interaction.user.id) in guild_data['users']:
        return True
    
    # Check if user has any authorized roles
    user_role_ids = [str(role.id) for role in interaction.user.roles]
    if any(role_id in guild_data['roles'] for role_id in user_role_ids):
        return True
    
    return False

async def log_auto_ban_action(guild: discord.Guild, user: discord.Member, content_type: str, message: discord.Message):
    """Log auto-ban actions to the designated log channel"""
    if not auto_ban_config.get('log_channel'):
        return
    
    try:
        log_channel = guild.get_channel(auto_ban_config['log_channel'])
        if log_channel:
            embed = discord.Embed(
                title="🚨 Auto-Ban Executed",
                color=0xff0000,
                timestamp=datetime.datetime.now()
            )
            embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=True)
            embed.add_field(name="Content Type", value=content_type, inline=True)
            embed.add_field(name="Channel", value=message.channel.mention, inline=True)
            
            if message.content:
                embed.add_field(name="Message", value=message.content[:500] + "..." if len(message.content) > 500 else message.content, inline=False)
            
            embed.add_field(name="Attachments", value=f"{len(message.attachments)} files", inline=True)
            
            await log_channel.send(embed=embed)
    except Exception as e:
        logging.error(f"Failed to log auto-ban action: {e}")

async def auto_ban_user(message: discord.Message, content_type: str):
    """Automatically ban user for posting prohibited content"""
    if not auto_ban_config.get('enabled', False):
        return
    
    user = message.author
    guild = message.guild
    
    # Check if user is exempt (has exempt roles)
    user_role_ids = [str(role.id) for role in user.roles]
    if any(role_id in auto_ban_config.get('exempt_roles', []) for role_id in user_role_ids):
        return
    
    # Check if channel is exempt
    if str(message.channel.id) in auto_ban_config.get('exempt_channels', []):
        return
    
    # Check if user is admin or bot
    if user.guild_permissions.administrator or user.bot:
        return
    
    try:
        # Try to send DM first
        ban_message = auto_ban_config.get('ban_message', "🚫 You have been automatically banned for posting prohibited content.")
        try:
            await user.send(f"{ban_message}\n**Server:** {guild.name}\n**Reason:** Posted {content_type}")
        except:
            pass  # Can't DM user, continue with ban
        
        # Ban from server
        await guild.ban(user, reason=f"Auto-ban: Posted {content_type}")
        
        # Log the action
        await log_auto_ban_action(guild, user, content_type, message)
        
        logging.info(f"🚨 Auto-banned user {user} ({user.id}) for posting {content_type} in {guild.name}")
        
    except discord.Forbidden:
        logging.error(f"❌ Missing permissions to ban user {user} in {guild.name}")
    except Exception as e:
        logging.error(f"❌ Failed to auto-ban user {user}: {e}")

@bot.event
async def on_ready():
    logging.info(f"🤖 Bot is ready! Logged in as {bot.user}")
    logging.info(f"📊 Connected to {len(bot.guilds)} guilds:")
    
    for guild in bot.guilds:
        logging.info(f" - {guild.name} (ID: {guild.id})")
    
    # Load data
    load_data()
    
    # Use global commands instead of guild-specific to avoid permission issues
    try:
        synced = await bot.tree.sync()
        logging.info(f"✅ Successfully synced {len(synced)} global commands")
    except Exception as e:
        logging.error(f"❌ Failed to sync commands: {e}")

# Global commands - work in all servers
@bot.tree.command(name="time", description="Get current time")
async def time(interaction: discord.Interaction):
    """Get current time"""
    if not is_authorized(interaction):
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
        return
        
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await interaction.response.send_message(f"🕒 {current_time}", ephemeral=True)

@bot.tree.command(name="user", description="Get user info")
async def user(interaction: discord.Interaction):
    """Get user info"""
    if not is_authorized(interaction):
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
        return
        
    await interaction.response.send_message(
        f"👤 **User Info:**\n"
        f"Name: {interaction.user.display_name}\n"
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
    
    if channel.id not in message_logs or not message_logs[channel.id]:
        await interaction.response.send_message(
            f"📭 No messages logged for {channel.mention}!\n"
            f"Use `/start_logging` first to begin logging this channel.",
            ephemeral=True
        )
        return
    
    log_text = f"**📝 Recent Messages in {channel.mention}:**\n\n"
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
            "📭 No channels are currently being logged.\n"
            "Use `/start_logging` in a channel to begin.",
            ephemeral=True
        )
        return
    
    status_text = "**📊 Currently Logging Channels:**\n\n"
    for channel_id, logs in message_logs.items():
        channel = interaction.guild.get_channel(channel_id)
        if channel:
            status_text += f"📝 {channel.mention} - {len(logs)} messages logged\n"
        else:
            status_text += f"❓ Unknown Channel (ID: {channel_id}) - {len(logs)} messages\n"
    
    await interaction.response.send_message(status_text, ephemeral=True)

# Auto-ban commands
@bot.tree.command(name="auto_ban_status", description="Check auto-ban configuration")
async def auto_ban_status(interaction: discord.Interaction):
    """Check auto-ban configuration"""
    if not is_authorized(interaction):
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
        return
    
    embed = discord.Embed(title="🛡️ Auto-Ban Configuration", color=0x00ff00)
    
    status = "✅ **ENABLED**" if auto_ban_config.get('enabled', False) else "❌ **DISABLED**"
    embed.add_field(name="Status", value=status, inline=False)
    
    content_types = ", ".join([f"`{ct}`" for ct in auto_ban_config.get('banned_content', [])])
    embed.add_field(name="Banned Content", value=content_types or "None", inline=False)
    
    log_channel_id = auto_ban_config.get('log_channel')
    if log_channel_id:
        log_channel = interaction.guild.get_channel(log_channel_id)
        embed.add_field(name="Log Channel", value=log_channel.mention if log_channel else f"Unknown ({log_channel_id})", inline=True)
    else:
        embed.add_field(name="Log Channel", value="Not set", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="auto_ban_enable", description="Enable auto-ban system")
async def auto_ban_enable(interaction: discord.Interaction):
    """Enable auto-ban system"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
        return
    
    auto_ban_config['enabled'] = True
    save_auto_ban_config()
    await interaction.response.send_message("✅ Auto-ban system **ENABLED**\n⚠️ Be careful - this will automatically ban users!", ephemeral=True)

@bot.tree.command(name="auto_ban_disable", description="Disable auto-ban system")
async def auto_ban_disable(interaction: discord.Interaction):
    """Disable auto-ban system"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
        return
    
    auto_ban_config['enabled'] = False
    save_auto_ban_config()
    await interaction.response.send_message("❌ Auto-ban system **DISABLED**", ephemeral=True)

@bot.tree.command(name="set_log_channel", description="Set channel for auto-ban logs")
@app_commands.describe(channel="The channel to send auto-ban logs to")
async def set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Set channel for auto-ban logs"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
        return
    
    auto_ban_config['log_channel'] = channel.id
    save_auto_ban_config()
    await interaction.response.send_message(f"✅ Auto-ban logs will be sent to {channel.mention}", ephemeral=True)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Auto-ban detection
    if auto_ban_config.get('enabled', False):
        content_detected = []
        
        # Check for images, GIFs, videos, files
        for attachment in message.attachments:
            lower_name = attachment.filename.lower()
            if any(ext in lower_name for ext in ['.png', '.jpg', '.jpeg', '.bmp', '.webp']):
                content_detected.append('image')
            elif '.gif' in lower_name:
                content_detected.append('gif')
            elif any(ext in lower_name for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']):
                content_detected.append('video')
            elif any(ext in lower_name for ext in ['.exe', '.bat', '.cmd', '.msi']):
                content_detected.append('executable')
            else:
                content_detected.append('file')
        
        # Auto-ban for detected content
        banned_types = auto_ban_config.get('banned_content', ['image', 'gif', 'video', 'file'])
        for content_type in content_detected:
            if content_type in banned_types:
                await auto_ban_user(message, content_type)
                break

    # Message logging
    if message.channel.id in message_logs:
        log_entry = {
            'author': str(message.author),
            'content': message.content,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'attachments': len(message.attachments)
        }
        
        message_logs[message.channel.id].append(log_entry)
        if len(message_logs[message.channel.id]) > 100:
            message_logs[message.channel.id].pop(0)
        
        logging.info(f"[{message.channel.name}] {log_entry['author']}: {log_entry['content']} [Files: {log_entry['attachments']}]")
    
    await bot.process_commands(message)

def run_bot():
    """Run the Discord bot"""
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        logging.error("❌ No Discord token found!")
        return
    
    try:
        asyncio.run(bot.start(TOKEN))
    except Exception as e:
        logging.error(f"❌ Error starting bot: {e}")

if __name__ == "__main__":
    # Start the bot in a separate thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logging.info("🤖 Discord bot started in background thread")
    
    # Keep the main thread alive
    try:
        while True:
            pass
    except KeyboardInterrupt:
        logging.info("👋 Shutting down...")
