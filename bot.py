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
from typing import Optional, List

# Load .env file if it exists
load_dotenv()

# Setup logging with better formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Bot initialization
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# Guild IDs
TEST_GUILD_ID = 1087033723347808317
SECOND_GUILD_ID = 1342381217672200274
TEST_GUILD = discord.Object(id=TEST_GUILD_ID)
SECOND_GUILD = discord.Object(id=SECOND_GUILD_ID)

# Data stores
message_logs = {}
authorized_data = {}
auto_ban_config = {}
ban_statistics = {'total_bans': 0, 'bans_by_type': {}, 'bans_by_user': {}}

# ===== DATA MANAGEMENT =====

def load_data():
    """Load all persistent data from files"""
    global authorized_data, auto_ban_config, ban_statistics
    
    # Load authorized data
    try:
        with open('authorized.json', 'r') as f:
            authorized_data = json.load(f)
        logging.info("✅ Loaded authorized data")
    except FileNotFoundError:
        authorized_data = {}
        logging.info("ℹ️  Creating new authorized data file")
        save_authorized_data()
    
    # Load auto-ban config
    try:
        with open('auto_ban_config.json', 'r') as f:
            auto_ban_config = json.load(f)
        logging.info("✅ Loaded auto-ban config")
    except FileNotFoundError:
        auto_ban_config = {
            'enabled': True,
            'ban_message': "🚫 You have been automatically banned for posting prohibited content.",
            'log_channel': None,
            'banned_content': ['image', 'gif', 'video', 'file'],
            'exempt_roles': [],
            'exempt_channels': [],
            'delete_messages': True,
            'notify_user': True
        }
        save_auto_ban_config()
    
    # Load ban statistics
    try:
        with open('ban_statistics.json', 'r') as f:
            ban_statistics = json.load(f)
        logging.info("✅ Loaded ban statistics")
    except FileNotFoundError:
        ban_statistics = {'total_bans': 0, 'bans_by_type': {}, 'bans_by_user': {}}
        save_ban_statistics()

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

def save_ban_statistics():
    """Save ban statistics to file"""
    try:
        with open('ban_statistics.json', 'w') as f:
            json.dump(ban_statistics, f, indent=2)
    except Exception as e:
        logging.error(f"❌ Failed to save ban statistics: {e}")

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
    """Check if user is authorized to use admin commands"""
    guild_data = get_guild_data(interaction.guild_id)
    
    if str(interaction.user.id) in guild_data['users']:
        return True
    
    user_role_ids = [str(role.id) for role in interaction.user.roles]
    if any(role_id in guild_data['roles'] for role_id in user_role_ids):
        return True
    
    if interaction.user.guild_permissions.administrator:
        return True
    
    return False

# ===== AUTO-BAN SYSTEM =====

async def log_auto_ban_action(guild: discord.Guild, user: discord.Member, content_type: str, message: discord.Message):
    """Log auto-ban actions with enhanced details"""
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
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.add_field(name="👤 User", value=f"{user.mention}\n`{user.name}` ({user.id})", inline=True)
            embed.add_field(name="📝 Content Type", value=f"`{content_type.upper()}`", inline=True)
            embed.add_field(name="📍 Channel", value=message.channel.mention, inline=True)
            
            content = message.content or "*No text content*"
            if len(content) > 1024:
                content = content[:1021] + "..."
            embed.add_field(name="💬 Message", value=content, inline=False)
            
            embed.add_field(name="📎 Attachments", value=str(len(message.attachments)), inline=True)
            embed.add_field(name="🖼️ Embeds", value=str(len(message.embeds)), inline=True)
            embed.add_field(name="🔗 Message Link", value=f"[Jump]({message.jump_url})", inline=True)
            
            # Add account age
            account_age = (datetime.datetime.now() - user.created_at).days
            embed.add_field(name="📅 Account Age", value=f"{account_age} days", inline=True)
            
            # Add join date
            if user.joined_at:
                join_age = (datetime.datetime.now() - user.joined_at).days
                embed.add_field(name="🏠 Member For", value=f"{join_age} days", inline=True)
            
            embed.set_footer(text=f"Total Bans: {ban_statistics['total_bans']}")
            
            await log_channel.send(embed=embed)
    except Exception as e:
        logging.error(f"❌ Failed to log auto-ban action: {e}")

async def auto_ban_user(message: discord.Message, content_type: str):
    """Automatically ban user with improved error handling"""
    if not auto_ban_config.get('enabled', True):
        return
    
    user = message.author
    guild = message.guild
    
    # Skip bots
    if user.bot:
        return
    
    # Check exempt roles
    user_role_ids = [str(role.id) for role in user.roles]
    if any(role_id in auto_ban_config.get('exempt_roles', []) for role_id in user_role_ids):
        logging.info(f"⏭️  Skipped ban for {user.name} (exempt role)")
        return
    
    # Check exempt channels
    if str(message.channel.id) in auto_ban_config.get('exempt_channels', []):
        logging.info(f"⏭️  Skipped ban in {message.channel.name} (exempt channel)")
        return
    
    # Skip administrators
    if user.guild_permissions.administrator:
        logging.info(f"⏭️  Skipped ban for {user.name} (administrator)")
        return
    
    try:
        # Delete message first if configured
        if auto_ban_config.get('delete_messages', True):
            try:
                await message.delete()
                logging.info(f"🗑️  Deleted message from {user.name}")
            except discord.Forbidden:
                logging.warning(f"⚠️  Cannot delete message from {user.name} (missing permissions)")
        
        # Notify user if configured
        if auto_ban_config.get('notify_user', True):
            try:
                ban_message = auto_ban_config.get('ban_message', "You have been banned for posting prohibited content.")
                await user.send(
                    f"{ban_message}\n\n"
                    f"**Server:** {guild.name}\n"
                    f"**Reason:** Posted {content_type}\n"
                    f"**Time:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            except discord.Forbidden:
                logging.warning(f"⚠️  Cannot DM {user.name} (DMs closed)")
        
        # Ban from server
        await guild.ban(user, reason=f"Auto-ban: Posted {content_type}", delete_message_days=1)
        
        # Update statistics
        ban_statistics['total_bans'] += 1
        ban_statistics['bans_by_type'][content_type] = ban_statistics['bans_by_type'].get(content_type, 0) + 1
        ban_statistics['bans_by_user'][str(user.id)] = ban_statistics['bans_by_user'].get(str(user.id), 0) + 1
        save_ban_statistics()
        
        # Log the action
        await log_auto_ban_action(guild, user, content_type, message)
        
        logging.info(f"🚨 Auto-banned {user.name} ({user.id}) for posting {content_type} in {guild.name}")
        
    except discord.Forbidden:
        logging.error(f"❌ Missing permissions to ban {user.name} in {guild.name}")
    except Exception as e:
        logging.error(f"❌ Failed to auto-ban {user.name}: {e}")

# ===== BOT EVENTS =====

@bot.event
async def on_ready():
    logging.info(f"🤖 Bot ready! Logged in as {bot.user}")
    logging.info(f"📊 Connected to {len(bot.guilds)} guild(s)")
    
    for guild in bot.guilds:
        member_count = guild.member_count
        logging.info(f"   └─ {guild.name} (ID: {guild.id}) | {member_count} members")
    
    load_data()
    
    # Sync commands
    await sync_guild_commands(TEST_GUILD, "Test Guild")
    await sync_guild_commands(SECOND_GUILD, "Second Guild")
    
    logging.info("✅ Bot initialization complete!")

async def sync_guild_commands(guild, guild_name):
    """Sync commands to a specific guild with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            logging.info(f"✅ Synced {len(synced)} command(s) to {guild_name}")
            return True
        except discord.Forbidden:
            logging.error(f"❌ Missing permissions in {guild_name}")
            return False
        except Exception as e:
            if attempt < max_retries - 1:
                logging.warning(f"⚠️  Retry {attempt + 1}/{max_retries} for {guild_name}: {e}")
                await asyncio.sleep(2)
            else:
                logging.error(f"❌ Failed to sync to {guild_name} after {max_retries} attempts: {e}")
                return False

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Auto-ban system
    if auto_ban_config.get('enabled', True) and message.guild:
        content_detected = []
        
        # Check attachments
        for attachment in message.attachments:
            filename = attachment.filename.lower()
            if filename.endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                if 'image' not in content_detected:
                    content_detected.append('image')
            elif filename.endswith('.gif'):
                if 'gif' not in content_detected:
                    content_detected.append('gif')
            elif filename.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv')):
                if 'video' not in content_detected:
                    content_detected.append('video')
            else:
                if 'file' not in content_detected and not content_detected:
                    content_detected.append('file')
        
        # Check embeds
        if message.embeds:
            for embed in message.embeds:
                if embed.image or embed.thumbnail:
                    if 'image' not in content_detected:
                        content_detected.append('embed_image')
        
        # Auto-ban for detected content
        banned_types = auto_ban_config.get('banned_content', ['image', 'gif', 'video', 'file'])
        for content_type in content_detected:
            if content_type in banned_types or (content_type == 'embed_image' and 'image' in banned_types):
                await auto_ban_user(message, content_type)
                return  # Stop processing after ban
    
    # Message logging
    if message.channel.id in message_logs:
        log_entry = {
            'author': str(message.author),
            'author_id': str(message.author.id),
            'content': message.content,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'attachments': len(message.attachments),
            'embeds': len(message.embeds),
            'message_id': str(message.id)
        }
        
        message_logs[message.channel.id].append(log_entry)
        if len(message_logs[message.channel.id]) > 100:
            message_logs[message.channel.id].pop(0)
        
        logging.info(f"📝 [{message.channel.name}] {log_entry['author']}: {log_entry['content'][:50]}")
    
    await bot.process_commands(message)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    logging.error(f"❌ Command error: {error}")
    
    if interaction.response.is_done():
        await interaction.followup.send("❌ Something went wrong!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Something went wrong!", ephemeral=True)

# ===== COMMANDS =====

@bot.tree.command(name="resync", description="🔄 Resync slash commands (Admin only)")
async def resync(interaction: discord.Interaction):
    """Resync all slash commands"""
    if not is_authorized(interaction):
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    success_count = 0
    fail_count = 0
    
    # Sync to current guild
    try:
        bot.tree.copy_global_to(guild=interaction.guild)
        synced = await bot.tree.sync(guild=interaction.guild)
        success_count += 1
        result_msg = f"✅ Synced {len(synced)} command(s) to this server\n"
    except Exception as e:
        fail_count += 1
        result_msg = f"❌ Failed to sync to this server: {e}\n"
    
    # Sync globally
    try:
        global_synced = await bot.tree.sync()
        result_msg += f"🌐 Synced {len(global_synced)} global command(s)\n"
        success_count += 1
    except Exception as e:
        result_msg += f"❌ Failed global sync: {e}\n"
        fail_count += 1
    
    embed = discord.Embed(
        title="🔄 Command Sync Results",
        description=result_msg,
        color=0x00ff00 if fail_count == 0 else 0xff9900,
        timestamp=datetime.datetime.now()
    )
    embed.set_footer(text=f"Success: {success_count} | Failed: {fail_count}")
    
    await interaction.followup.send(embed=embed, ephemeral=True)
    logging.info(f"🔄 Commands resynced by {interaction.user.name}")

@bot.tree.command(name="auto_ban_status", description="📊 Check auto-ban configuration")
async def auto_ban_status(interaction: discord.Interaction):
    if not is_authorized(interaction):
        await interaction.response.send_message("❌ No permission!", ephemeral=True)
        return
    
    embed = discord.Embed(title="🛡️ Auto-Ban System Status", color=0x00ff00 if auto_ban_config.get('enabled') else 0xff0000)
    
    status = "✅ **ENABLED**" if auto_ban_config.get('enabled', True) else "❌ **DISABLED**"
    embed.add_field(name="Status", value=status, inline=False)
    
    content_types = ", ".join([f"`{ct}`" for ct in auto_ban_config.get('banned_content', [])])
    embed.add_field(name="🚫 Banned Content", value=content_types or "None", inline=False)
    
    # Log channel
    log_channel_id = auto_ban_config.get('log_channel')
    if log_channel_id:
        log_channel = interaction.guild.get_channel(log_channel_id)
        embed.add_field(name="📝 Log Channel", value=log_channel.mention if log_channel else "❌ Not found", inline=True)
    else:
        embed.add_field(name="📝 Log Channel", value="❌ Not set", inline=True)
    
    # Statistics
    embed.add_field(name="📊 Total Bans", value=str(ban_statistics['total_bans']), inline=True)
    embed.add_field(name="👥 Exempt Roles", value=str(len(auto_ban_config.get('exempt_roles', []))), inline=True)
    embed.add_field(name="📍 Exempt Channels", value=str(len(auto_ban_config.get('exempt_channels', []))), inline=True)
    
    # Settings
    delete_msg = "✅ Yes" if auto_ban_config.get('delete_messages', True) else "❌ No"
    notify_user = "✅ Yes" if auto_ban_config.get('notify_user', True) else "❌ No"
    embed.add_field(name="🗑️ Delete Messages", value=delete_msg, inline=True)
    embed.add_field(name="📧 Notify Users", value=notify_user, inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ban_stats", description="📈 View ban statistics")
async def ban_stats(interaction: discord.Interaction):
    if not is_authorized(interaction):
        await interaction.response.send_message("❌ No permission!", ephemeral=True)
        return
    
    embed = discord.Embed(title="📈 Ban Statistics", color=0x3498db, timestamp=datetime.datetime.now())
    
    embed.add_field(name="Total Bans", value=f"**{ban_statistics['total_bans']}**", inline=False)
    
    if ban_statistics['bans_by_type']:
        types_text = "\n".join([f"`{k}`: {v}" for k, v in ban_statistics['bans_by_type'].items()])
        embed.add_field(name="Bans by Content Type", value=types_text, inline=False)
    
    if ban_statistics['bans_by_user']:
        top_banned = sorted(ban_statistics['bans_by_user'].items(), key=lambda x: x[1], reverse=True)[:5]
        users_text = "\n".join([f"<@{uid}>: {count}" for uid, count in top_banned])
        embed.add_field(name="Top Banned Users", value=users_text, inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="auto_ban_enable", description="✅ Enable auto-ban system")
async def auto_ban_enable(interaction: discord.Interaction):
    if not is_authorized(interaction):
        await interaction.response.send_message("❌ No permission!", ephemeral=True)
        return
    
    auto_ban_config['enabled'] = True
    save_auto_ban_config()
    await interaction.response.send_message("✅ Auto-ban system **ENABLED**", ephemeral=True)
    logging.info(f"✅ Auto-ban enabled by {interaction.user.name}")

@bot.tree.command(name="auto_ban_disable", description="❌ Disable auto-ban system")
async def auto_ban_disable(interaction: discord.Interaction):
    if not is_authorized(interaction):
        await interaction.response.send_message("❌ No permission!", ephemeral=True)
        return
    
    auto_ban_config['enabled'] = False
    save_auto_ban_config()
    await interaction.response.send_message("❌ Auto-ban system **DISABLED**", ephemeral=True)
    logging.info(f"❌ Auto-ban disabled by {interaction.user.name}")

@bot.tree.command(name="set_log_channel", description="📝 Set channel for auto-ban logs")
@app_commands.describe(channel="The channel to send logs to")
async def set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_authorized(interaction):
        await interaction.response.send_message("❌ No permission!", ephemeral=True)
        return
    
    auto_ban_config['log_channel'] = channel.id
    save_auto_ban_config()
    await interaction.response.send_message(f"✅ Logs will be sent to {channel.mention}", ephemeral=True)

@bot.tree.command(name="authorize_user", description="👤 Add user to authorized list")
@app_commands.describe(user="User to authorize")
async def authorize_user(interaction: discord.Interaction, user: discord.Member):
    if not is_authorized(interaction):
        await interaction.response.send_message("❌ No permission!", ephemeral=True)
        return
    
    guild_data = get_guild_data(interaction.guild_id)
    user_id = str(user.id)
    
    if user_id not in guild_data['users']:
        guild_data['users'].append(user_id)
        save_authorized_data()
        await interaction.response.send_message(f"✅ {user.mention} authorized!", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ {user.mention} already authorized!", ephemeral=True)

@bot.tree.command(name="ping", description="🏓 Check bot latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency: **{latency}ms**", ephemeral=True)

# ===== MAIN =====

async def main():
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        raise ValueError("❌ No Discord token found in environment variables!")
    
    try:
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        logging.info("🛑 Bot stopped by user")
    except Exception as e:
        logging.error(f"❌ Error starting bot: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Shutting down...")
