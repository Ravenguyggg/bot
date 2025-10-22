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
            'enabled': True,
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
        logging.info("💾 Saved authorized data to file")
    except Exception as e:
        logging.error(f"❌ Failed to save authorized data: {e}")

def save_auto_ban_config():
    """Save auto-ban configuration to file"""
    try:
        with open('auto_ban_config.json', 'w') as f:
            json.dump(auto_ban_config, f, indent=2)
        logging.info("💾 Saved auto-ban config to file")
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
            embed.add_field(name="Message", value=message.content or "*No text content*", inline=False)
            embed.add_field(name="Attachments", value=f"{len(message.attachments)} files", inline=True)
            embed.add_field(name="Embeds", value=f"{len(message.embeds)} embeds", inline=True)
            
            # Add message link if available
            if message.channel and message.id:
                embed.add_field(name="Message Link", value=f"[Jump to Message]({message.jump_url})", inline=False)
            
            await log_channel.send(embed=embed)
    except Exception as e:
        logging.error(f"Failed to log auto-ban action: {e}")

async def auto_ban_user(message: discord.Message, content_type: str):
    """Automatically ban user for posting prohibited content"""
    if not auto_ban_config.get('enabled', True):
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
        # Ban the user
        ban_message = auto_ban_config.get('ban_message', "🚫 You have been automatically banned for posting prohibited content.")
        await user.send(f"{ban_message}\n**Server:** {guild.name}\n**Reason:** Posted {content_type}")
        
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
    logging.info(f"Bot is ready! Logged in as {bot.user}")
    logging.info(f"Connected to {len(bot.guilds)} guilds:")
    
    for guild in bot.guilds:
        logging.info(f" - {guild.name} (ID: {guild.id})")
    
    # Load data
    load_data()
    
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
    
    # Existing commands (time, user, logs, start_logging, stop_logging, logging_status)
    # ... [Keep all your existing commands here] ...
    
    # AUTO-BAN MANAGEMENT COMMANDS
    @bot.tree.command(name="auto_ban_status", description="Check auto-ban configuration")
    async def auto_ban_status(interaction: discord.Interaction):
        """Check auto-ban configuration"""
        if not is_authorized(interaction):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
        
        embed = discord.Embed(title="🛡️ Auto-Ban Configuration", color=0x00ff00)
        
        # Status
        status = "✅ **ENABLED**" if auto_ban_config.get('enabled', True) else "❌ **DISABLED**"
        embed.add_field(name="Status", value=status, inline=False)
        
        # Banned content types
        content_types = ", ".join([f"`{ct}`" for ct in auto_ban_config.get('banned_content', [])])
        embed.add_field(name="Banned Content", value=content_types or "None", inline=False)
        
        # Log channel
        log_channel_id = auto_ban_config.get('log_channel')
        if log_channel_id:
            log_channel = interaction.guild.get_channel(log_channel_id)
            embed.add_field(name="Log Channel", value=log_channel.mention if log_channel else f"Unknown ({log_channel_id})", inline=True)
        else:
            embed.add_field(name="Log Channel", value="Not set", inline=True)
        
        # Exempt roles count
        exempt_roles = len(auto_ban_config.get('exempt_roles', []))
        embed.add_field(name="Exempt Roles", value=str(exempt_roles), inline=True)
        
        # Exempt channels count
        exempt_channels = len(auto_ban_config.get('exempt_channels', []))
        embed.add_field(name="Exempt Channels", value=str(exempt_channels), inline=True)
        
        # Ban message preview
        ban_msg = auto_ban_config.get('ban_message', 'Not set')
        if len(ban_msg) > 100:
            ban_msg = ban_msg[:100] + "..."
        embed.add_field(name="Ban Message", value=f"`{ban_msg}`", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="auto_ban_enable", description="Enable auto-ban system")
    async def auto_ban_enable(interaction: discord.Interaction):
        """Enable auto-ban system"""
        if not is_authorized(interaction):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
        
        auto_ban_config['enabled'] = True
        save_auto_ban_config()
        await interaction.response.send_message("✅ Auto-ban system **ENABLED**", ephemeral=True)

    @bot.tree.command(name="auto_ban_disable", description="Disable auto-ban system")
    async def auto_ban_disable(interaction: discord.Interaction):
        """Disable auto-ban system"""
        if not is_authorized(interaction):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
        
        auto_ban_config['enabled'] = False
        save_auto_ban_config()
        await interaction.response.send_message("❌ Auto-ban system **DISABLED**", ephemeral=True)

    @bot.tree.command(name="set_ban_message", description="Set custom ban message")
    @app_commands.describe(message="The message to send when banning users")
    async def set_ban_message(interaction: discord.Interaction, message: str):
        """Set custom ban message"""
        if not is_authorized(interaction):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
        
        auto_ban_config['ban_message'] = message
        save_auto_ban_config()
        await interaction.response.send_message(f"✅ Ban message set to: `{message}`", ephemeral=True)

    @bot.tree.command(name="set_log_channel", description="Set channel for auto-ban logs")
    @app_commands.describe(channel="The channel to send auto-ban logs to")
    async def set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        """Set channel for auto-ban logs"""
        if not is_authorized(interaction):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
        
        auto_ban_config['log_channel'] = channel.id
        save_auto_ban_config()
        await interaction.response.send_message(f"✅ Auto-ban logs will be sent to {channel.mention}", ephemeral=True)

    @bot.tree.command(name="add_exempt_role", description="Add role to auto-ban exempt list")
    @app_commands.describe(role="The role to exempt from auto-ban")
    async def add_exempt_role(interaction: discord.Interaction, role: discord.Role):
        """Add role to auto-ban exempt list"""
        if not is_authorized(interaction):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
        
        role_id = str(role.id)
        if role_id not in auto_ban_config.get('exempt_roles', []):
            auto_ban_config.setdefault('exempt_roles', []).append(role_id)
            save_auto_ban_config()
            await interaction.response.send_message(f"✅ Added {role.mention} to exempt roles", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {role.mention} is already exempt", ephemeral=True)

    @bot.tree.command(name="remove_exempt_role", description="Remove role from auto-ban exempt list")
    @app_commands.describe(role="The role to remove from exempt list")
    async def remove_exempt_role(interaction: discord.Interaction, role: discord.Role):
        """Remove role from auto-ban exempt list"""
        if not is_authorized(interaction):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
        
        role_id = str(role.id)
        if role_id in auto_ban_config.get('exempt_roles', []):
            auto_ban_config['exempt_roles'].remove(role_id)
            save_auto_ban_config()
            await interaction.response.send_message(f"✅ Removed {role.mention} from exempt roles", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {role.mention} is not in exempt roles", ephemeral=True)

    @bot.tree.command(name="add_exempt_channel", description="Add channel to auto-ban exempt list")
    @app_commands.describe(channel="The channel to exempt from auto-ban")
    async def add_exempt_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        """Add channel to auto-ban exempt list"""
        if not is_authorized(interaction):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
        
        channel_id = str(channel.id)
        if channel_id not in auto_ban_config.get('exempt_channels', []):
            auto_ban_config.setdefault('exempt_channels', []).append(channel_id)
            save_auto_ban_config()
            await interaction.response.send_message(f"✅ Added {channel.mention} to exempt channels", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {channel.mention} is already exempt", ephemeral=True)

    @bot.tree.command(name="remove_exempt_channel", description="Remove channel from auto-ban exempt list")
    @app_commands.describe(channel="The channel to remove from exempt list")
    async def remove_exempt_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        """Remove channel from auto-ban exempt list"""
        if not is_authorized(interaction):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
        
        channel_id = str(channel.id)
        if channel_id in auto_ban_config.get('exempt_channels', []):
            auto_ban_config['exempt_channels'].remove(channel_id)
            save_auto_ban_config()
            await interaction.response.send_message(f"✅ Removed {channel.mention} from exempt channels", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {channel.mention} is not in exempt channels", ephemeral=True)

    @bot.tree.command(name="view_banned_content", description="View what content types are auto-banned")
    async def view_banned_content(interaction: discord.Interaction):
        """View what content types are auto-banned"""
        if not is_authorized(interaction):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
        
        content_types = auto_ban_config.get('banned_content', ['image', 'gif', 'video', 'file'])
        embed = discord.Embed(title="🚫 Banned Content Types", color=0xff0000)
        
        for content_type in content_types:
            embed.add_field(
                name=content_type.upper(),
                value="✅ Will auto-ban" if auto_ban_config.get('enabled', True) else "❌ Auto-ban disabled",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Setup all commands
setup_commands()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Auto-detect and handle banned content
    if auto_ban_config.get('enabled', True):
        content_detected = []
        
        # Check for images
        if any(attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')) for attachment in message.attachments):
            content_detected.append('image')
        
        # Check for GIFs
        if any(attachment.filename.lower().endswith('.gif') for attachment in message.attachments):
            content_detected.append('gif')
        
        # Check for videos
        if any(attachment.filename.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')) for attachment in message.attachments):
            content_detected.append('video')
        
        # Check for files
        if message.attachments and not content_detected:
            content_detected.append('file')
        
        # Check for embeds (often contain images/gifs)
        if message.embeds:
            content_detected.append('embed')
        
        # Auto-ban for detected content
        banned_types = auto_ban_config.get('banned_content', ['image', 'gif', 'video', 'file'])
        for content_type in content_detected:
            if content_type in banned_types:
                await auto_ban_user(message, content_type)
                break  # Only ban once per message

    # Only log if channel is being monitored (your existing logging)
    if message.channel.id in message_logs:
        log_entry = {
            'author': str(message.author),
            'content': message.content,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'attachments': len(message.attachments),
            'embeds': len(message.embeds)
        }
        
        message_logs[message.channel.id].append(log_entry)
        # Keep only last 100 messages per channel
        if len(message_logs[message.channel.id]) > 100:
            message_logs[message.channel.id].pop(0)
        
        logging.info(f"[{message.channel.name}] [{log_entry['timestamp']}] {log_entry['author']}: {log_entry['content']} [Attachments: {log_entry['attachments']}]")
    
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
