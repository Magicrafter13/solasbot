#!/usr/bin/python3
"""Bot for various administrative duties in The Solas Council."""

import asyncio
import logging
import math
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord import app_commands, Client, Guild, Intents, Interaction, Member, User

from config import TOKEN, PRIMARY_GUILD, LOGGING, EXTRA_GUILDS, SERVER_NAME

logging.basicConfig(level=logging.INFO)
sys.stdout.reconfigure(line_buffering=True)

# Config

DRY_RUN = os.environ.get('DRY_RUN', 'False').lower() == 'true'

# Discord Stuff

intents = Intents.default()
intents.message_content = True
intents.messages = True
intents.members = True
#intents.reactions = True
client = Client(intents=intents, max_messages=5000)
tree = app_commands.CommandTree(client)

COLORS = {
    'ban': 0xe01b24,
    'kick': 0xff7800,
    'timeout': 0xf6d32d,
    'event': 0x986a44,
    'unban': 0x33d17a,

    'member_join': 0x26a269,
    'member_leave': 0xa51d2d,
}

# Connect to local database
CONN = sqlite3.connect('users.db')
CURSOR = CONN.cursor()
# Create tables if they don't exist
CURSOR.execute('''
    CREATE TABLE IF NOT EXISTS bans (
        user INT NOT NULL PRIMARY KEY,
        date TIMESTAMP
    );''')

# Helper functions

async def try_authorization(interaction: Interaction, user: Optional[Member | User]=None) -> bool:
    """Check if user is authorized to run command, inform them if they aren't."""
    # If argument is a User type, see if it can be resolved to a Member type. If not, return true.
    if (isinstance(user, User) or interaction.guild.id != PRIMARY_GUILD['id']):
        try:
            member = await client.primary_guild.fetch_member(user.id)
            user = member
        except discord.NotFound:
            return True

    # user is now type Member

    # Check that they are an administrator/moderator
    runner = await client.primary_guild.fetch_member(interaction.user.id)
    if not PRIMARY_GUILD['staff_role_id'] in [role.id for role in runner.roles]:
        await interaction.response.send_message(
            'You are not authorized to use this command!',
            ephemeral=True)
        return False
    # If the interaction involves another user, make sure that they are within the bot's
    # jurisdiction
    if user:
        guild_roles = [role.id for role in client.primary_guild.roles]
        if guild_roles.index(user.roles[-1].id) > guild_roles.index(PRIMARY_GUILD['max_bannable_role_id']):  # pylint: disable=line-too-long
            await interaction.response.send_message(
                f'You are not allowed to run `/{interaction.command.name}` on this user due to their roles.',  # pylint: disable=line-too-long
                ephemeral=True)
            return False
    return True

async def send_dm(user: User, message: str) -> bool:
    """Send a DM to a user (creating the channel if necessary)."""
    dm = user.dm_channel
    try:
        if not user.dm_channel:
            dm = await user.create_dm()
        await dm.send(message)
    except discord.HTTPException as _e:
        print(_e)
        return False
    except discord.Forbidden as _e:
        print(_e)
        return False
    except discord.NotFound as _e:
        print(_e)
        return False
    return True

def remove_from_db(user: User):
    """Remove a user.id from the SQLite database."""
    CURSOR.execute(
        '''
            DELETE FROM bans
            WHERE user = ?;
        ''',
        (user.id,)
    )
    CONN.commit()

async def log_action(action: str, user: Member, info: Optional[str]='', color: Optional[int]=COLORS['event']):
    """Log a bot action, with optional additional information."""
    embed = discord.Embed(
        title=f'Action: `{action}`',
        description=info,
        colour=color,
        timestamp=datetime.now())
    embed.set_author(name=f'{user.display_name}', icon_url=user.avatar.url if user.avatar else None)
    embed.set_footer(text="Moderator Action Log Item")

    await client.logging_channels['mod_actions'].send(user.mention, embed=embed)

# Bot commands

@tree.command(name='ban', description='3 month ban')
@app_commands.describe(user='Username to ban.', type='Type of ban to issue.', reason='Optional, additional, reason for banning (will be sent to the banned user).')
@app_commands.choices(type=[
    app_commands.Choice(name='3-month ban (class 1 infraction).', value='ban'),
    app_commands.Choice(name="Bot/Spam/Scam account perma-ban (doesn't DM reason, deletes 7-days of their messages).", value='spam'),
    app_commands.Choice(name='Permanently ban a regular user (blacklist).', value='blacklist')
])
async def ban(interaction: Interaction, user: User, type: str, reason: Optional[str]='none given'):
    """Add user to ban database, and then bans them."""
    if await try_authorization(interaction, user) is False:
        return

    dm_message = ''
    match type:
        case 'ban':
            dm_message = (
                f'You have receive a 3-month ban from {SERVER_NAME}.\n'
                'Given reason:\n'
                f'> {reason}'
            )
        case 'blacklist':
            dm_message = (
                f'You have been permanently blacklisted from {SERVER_NAME}.\n'
                'Given reason:\n'
                f'> {reason}'
            )

    # DM banee
    got_dm = True
    if dm_message != '' and not await send_dm(user, dm_message):
        got_dm = False
        await interaction.channel.send(f'Failed to DM {user}, check logs.')

    # Add to database
    if type == 'ban':
        CURSOR.execute(
            '''
                INSERT INTO bans
                VALUES (?, date('now'))
                ON CONFLICT (user) DO
                    UPDATE SET date = date('now');
            ''',
            (user.id,))
        CONN.commit()
    # Remove from database if permanent ban and already there
    else:
        remove_from_db(user)

    # Ban user
    if DRY_RUN:
        return
    try:
        await client.primary_guild.ban(
            user,
            reason=reason,
            delete_message_seconds=(604800 if type == 'spam' else 0))
    except discord.Forbidden:
        return await interaction.response.send_message(f'Lacking permissions to ban {user}!')
    except Exception as _e:
        return print(f'EXCEPTION IN /ban:\n{_e}')

    user_info = f'{user.mention} (`{user.id}`)'

    action = 'ban'
    match type:
        case 'ban':
            action = '3-month ban'
        case 'blacklist':
            action = 'blacklist'
    await log_action(
        action,
        interaction.user,
        info=f"user banned: {user_info}\nreason:\n> {reason}\nSuccessfully DM'd: {got_dm}",
        color=COLORS['ban'])
    return await interaction.response.send_message(
        f'Banned {user_info} with reason `{reason}`.')

@tree.command(name='kick', description='Kick someone from the server.')
@app_commands.describe(user='Member to kick.', reason='Optional reason for kicking.')
async def kick(interaction: Interaction, user: Member|User, reason: Optional[str]='none given'):
    """Kick user, and tell them why."""
    if await try_authorization(interaction, user) is False:
        return

    # DM kickee
    got_dm = True
    if not await send_dm(
        user,
        f'You have been kicked from {SERVER_NAME}.\nGiven reason:\n> {reason}'
    ):
        got_dm = False
        await interaction.channel.send(f'Failed to DM {user}, check logs.')

    # Kick user
    if DRY_RUN:
        return
    try:
        await client.primary_guild.kick(user, reason=reason)
    except discord.Forbidden:
        return await interaction.response.send_message(f'Lacking permissions to kick {user}!')
    except Exception as _e:
        return print(f'EXCEPTION IN /kick:\n{_e}')

    user_info = f'{user.mention} (`{user.id}`)'

    await log_action(
        'kick',
        interaction.user,
        info=f"user kicked: {user_info}\nreason:\n> {reason}\nSuccessfully DM'd: {got_dm}",
        color=COLORS['kick'])
    return await interaction.response.send_message(
        f'Kicked {user_info} with reason `{reason}`.')

SOLAS_TIMEOUTS = {
    '1h': timedelta(hours=1),
    '24h': timedelta(days=1),
    '1w': timedelta(weeks=1),
    '10m': timedelta(minutes=10)
}

@tree.command(name='timeout', description='Silence a user from participating for a while.')
@app_commands.describe(
    user='Member to timeout.',
    time='How long to keep user timed out.',
    reason='Optional reason for timeout.'
)
@app_commands.choices(time=[
    app_commands.Choice(name='1 Hour', value='1h'),
    app_commands.Choice(name='24 Hours', value='24h'),
    app_commands.Choice(name='1 Week', value='1w'),
    app_commands.Choice(name='10 Minutes', value='10m')
])
async def timeout(
    interaction: Interaction,
    user: Member|User,
    time: str,
    reason: Optional[str]='none given'
):
    """Timeout user, and tell them why."""
    if await try_authorization(interaction, user) is False:
        return

    # DM rascal
    got_dm = True
    if not await send_dm(
        user,
        f'You have been timed out in {SERVER_NAME}.\nGiven reason:\n> {reason}'
    ):
        got_dm = False
        await interaction.channel.send(f'Failed to DM {user}, check logs.')

    # Timeout user
    try:
        user = await client.primary_guild.fetch_member(user.id)
    except NotFound:
        return await interaction.response.send_message(f'User is not a member in {SERVER_NAME}!')
    try:
        await user.timeout(SOLAS_TIMEOUTS[time], reason=reason)
    except discord.Forbidden:
        return await interaction.response.send_message(f'Lacking permissions to timeout {user}!')
    except Exception as _e:
        return print(f'EXCEPTION IN /timeout:\n{_e}')

    user_info = f'{user.mention} (`{user.id}`)'

    await log_action(
        'timeout',
        interaction.user,
        info=f"user timed out: {user_info}\nlength of time: {time}\nreason:\n> {reason}\nSuccessfully DM'd: {got_dm}",
        color=COLORS['timeout'])
    return await interaction.response.send_message(
        f'Timed out {user_info} for {time} with reason `{reason}`.')

@tree.command(name='clear', description='Delete all the messages in the current channel.')
async def clear(interaction: Interaction):
    """Delete every message in the channel, if it is in the whitelist."""
    if await try_authorization(interaction) is False:
        return

    if not interaction.channel_id in PRIMARY_GUILD['clear_channel_whitelist']:
        return await interaction.response.send_message(
            'You are not allowed to clear this channel!',
            ephemeral=True)

    await interaction.response.send_message('Clearing messages, please be patient.', ephemeral=True)

    if DRY_RUN:
        return
    try:
        async for message in interaction.channel.history(limit=None, oldest_first=True):
            await message.delete()
    except discord.Forbidden:
        return await interaction.followup.send('Unable to delete message(s).', ephemeral=True)
    except discord.HTTPException:
        return await interaction.followup.send('Unable to delete message(s).', ephemeral=True)

    await log_action(
        'channel clear',
        interaction.user,
        info=f'channel: https://discord.com/channels/{PRIMARY_GUILD["id"]}/{interaction.channel_id}')
    return await interaction.followup.send('Done!', ephemeral=True)

@tree.command(name='unban', description="Manually lift a user's ban.")
@app_commands.describe(
    user='Member to unban.',
    reason='Optional reason for unban (not sent to user).'
)
async def unban(interaction: Interaction, user: User, reason: Optional[str]):
    """Unban a user."""
    if await try_authorization(interaction, user) is False:
        return

    remove_from_db(user)

    # Unban user
    try:
        await client.primary_guild.unban(user, reason=reason)
    except discord.Forbidden:
        return await interaction.response.send_message(f'Lacking permissions to unban {user}!')
    except Exception as _e:
        return print(f'EXCEPTION IN /unban:\n{_e}')

    user_info = f'{user.mention} (`{user.id}`)'

    await log_action(
        'unban',
        interaction.user,
        info=f'user unbanned: {user_info}\nreason:\n> {reason}',
        color=COLORS['unban'])
    return await interaction.response.send_message(
        f'Unbanned {user_info} with reason `{reason}`.')

# Non commands

async def unban_users():
    """Wait until midnight, then unban relevant users."""
    while True:
        now = datetime.now()
        target = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        sleep_seconds = (target - now).total_seconds()
        logging.info('Waiting %s seconds before checking bans...', sleep_seconds)
        await asyncio.sleep(sleep_seconds)
        logging.info('Getting list of users to be unbanned')
        CURSOR.execute('''
            SELECT *
            FROM bans
            WHERE date < datetime('now', '-3 months');
        ''')
        pardons = CURSOR.fetchall()
        for user_id, _ in pardons:
            logging.info('Unbanning %s...', user_id)
            try:
                await client.primary_guild.unban(
                    await client.fetch_user(user_id),
                    reason='3-month ban expired')
                user_info = f'<@{user_id}> (`{user_id}`)'
                await log_action(
                    'unban',
                    client.user,
                    f'user unbanned: {user_info}\nreason:\n> 3-month ban has expired')
            except discord.NotFound:
                logging.warning("User wasn't banned!")
            remove_from_db(user)

# Events

@client.event
async def on_ready():
    """Initialize bot data and tasks."""
    logging.info('Logged in as %s.', client.user)
    client.primary_guild = await client.fetch_guild(PRIMARY_GUILD["id"])
    client.logging_channels = {
        log_type: await (await client.fetch_guild(guild_id)).fetch_channel(channel_id)
        for log_type, (guild_id, channel_id) in LOGGING.items()}
    client.loop.create_task(unban_users())
    await asyncio.sleep(5)
    await client.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"{SERVER_NAME} ({os.environ.get('VERSION', 'unspecified bot version')})"))
    await tree.sync()

@client.event
async def on_member_join(member: Member):
    """Log a member joining the guild."""
    if member.guild.id != client.primary_guild.id:
        return

    embed = discord.Embed(
        title='Member Join',
        description=f'{member.mention}\n{member.id}: `{member.name}`',
        colour=COLORS['member_join'],
        timestamp=datetime.now())
    embed.add_field(name='Joined Server', value=f'<t:{math.floor(member.joined_at.timestamp())}:D>', inline=True)
    embed.add_field(name='Joined Discord', value=f'<t:{math.floor(member.created_at.timestamp())}:D>', inline=True)
    if member.avatar:
        embed.set_image(url=member.avatar.url)
    embed.set_footer(text="Member Event Log Item")

    await client.logging_channels['member_join'].send(embed=embed)

@client.event
async def on_member_remove(member: Member):
    """Log a member leaving the guild."""
    if member.guild.id != client.primary_guild.id:
        return

    embed = discord.Embed(
        title='Member Leave',
        description=f'{member.mention}\n{member.id}: `{member.name}`',
        colour=COLORS['member_leave'],
        timestamp=datetime.now()
    )

    embed.add_field(name='Joined Server', value=f'<t:{math.floor(member.joined_at.timestamp())}:D>', inline=True)
    embed.add_field(name='Joined Discord', value=f'<t:{math.floor(member.created_at.timestamp())}:D>', inline=True)

    # Prepare a list of roles (excluding @everyone, which is default role)
    roles = []
    # Use role mentions if logging in the same server, otherwise resort to display names
    if client.logging_channels['member_leave'].id == client.primary_guild.id:
        roles = [role.mention for role in member.roles if role != member.guild.default_role]
    else:
        roles = [role.name for role in member.roles if role != member.guild.default_role]

    if roles:
        # Discord field values must be ≤ 1024 characters
        roles_str = ', '.join(roles)
        if len(roles_str) > 1024:
            roles_str = roles_str[:1021] + '...'
        embed.add_field(name='Roles', value=roles_str, inline=False)
    else:
        embed.add_field(name='Roles', value='No roles', inline=False)

    if member.avatar:
        embed.set_image(url=member.avatar.url)

    embed.set_footer(text="Member Event Log Item")

    await client.logging_channels['member_leave'].send(embed=embed)


@client.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    """Log changes to cached messages."""
    if (
        before.guild.id != client.primary_guild.id or
        before.author.bot or
        before.content == after.content
    ):
        return

    embed = discord.Embed(
        title="Message Edited",
        color=discord.Color.orange(),
        timestamp=datetime.now()  # or datetime.utcnow()
    )

    embed.description = (
        f"**Author:** {before.author.mention} (`{before.author}`)\n"
        f"**Channel:** {before.channel.mention} (`#{before.channel}`)"
    )

    embed.add_field(name="Before", value=before.content or "*[no content]*", inline=False)
    embed.add_field(name="After", value=after.content or "*[no content]*", inline=False)
    embed.add_field(
        name="Info",
        value=f"Message ID: {before.id} | [Jump]({after.jump_url})",
        inline=False)

    embed.set_footer(text='Message Event Log Item')

    await client.logging_channels['message_edit'].send(embed=embed)

@client.event
async def on_message_delete(message: discord.Message):
    """Log cached message deletions."""
    if message.guild.id != client.primary_guild.id or message.author.bot:
        return

    embed = discord.Embed(
        title="Message Deleted",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )

    embed.description = (
        f"**Author:** {message.author.mention} (`{message.author}`)\n"
        f"**Channel:** {message.channel.mention} (`#{message.channel}`)"
    )

    embed.add_field(name="Content", value=message.content or "*[no content]*", inline=False)
    embed.set_footer(text=f"Message ID: {message.id}")

    await client.logging_channels['messages_delete'].send(embed=embed)

@client.event
async def on_user_update(before: User, after: User):
    """Log changes to user's avatar."""
    if before.avatar == after.avatar:
        return

    embed = discord.Embed(
        title="Avatar Changed",
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )

    embed.set_author(name=str(after), icon_url=after.display_avatar.url)
    embed.set_thumbnail(url=before.display_avatar.url)
    embed.set_image(url=after.display_avatar.url)

    embed.description = f"**User:** {after.mention} (`{after}`)\n"
    embed.set_footer(text=f"User ID: {after.id}")

    await client.logging_channels['member_avatar'].send(embed=embed)

@client.event
async def on_member_update(before: Member, after: Member):
    """Log role and nickname changes."""
    if before.guild.id != client.primary_guild.id:
        return

    if set(before.roles) != set(after.roles):
        await handle_role_change(before, after)

    if before.nick != after.nick:
        await handle_nickname_change(before, after)

@client.event
async def on_member_ban(guild: Guild, user: User):
    """Log members not banned through the bot."""
    entry, _ = [entry async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban)]
    if entry.user != client.user and entry.target == user:
        return await log_action(
            'ban',
            entry.user,
            info=f"{entry.user.mention} possibly banned {user.mention} (`{user.id}`)",
            color=COLORS['ban'])

# Helper functions for multi-responsibility events
async def handle_role_change(before: Member, after: Member):
    """Log changes to member roles."""
    before_roles = set(before.roles)
    after_roles = set(after.roles)

    added_roles = after_roles - before_roles
    removed_roles = before_roles - after_roles

    embed = discord.Embed(
        title="Role Update",
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )

    embed.set_author(name=str(after), icon_url=after.display_avatar.url)
    embed.description = f"**Member:** {after.mention} (`{after}`)"

    if added_roles:
        # Use role mentions if logging in the same server, otherwise resort to display names
        if client.logging_channels['member_role'].id == client.primary_guild.id:
            embed.add_field(
                name="Roles Added",
                value=", ".join(role.mention for role in added_roles),
                inline=False
            )
        else:
            embed.add_field(
                name="Roles Added",
                value=", ".join(role.name for role in added_roles),
                inline=False
            )
    if removed_roles:
        # Use role mentions if logging in the same server, otherwise resort to display names
        if client.logging_channels['member_role'].id == client.primary_guild.id:
            embed.add_field(
                name="Roles Removed",
                value=", ".join(role.mention for role in removed_roles),
                inline=False
            )
        else:
            embed.add_field(
                name="Roles Removed",
                value=", ".join(role.name for role in removed_roles),
                inline=False
            )

    embed.set_footer(text=f"User ID: {after.id}")
    await client.logging_channels['member_role'].send(embed=embed)

async def handle_nickname_change(before: Member, after: Member):
    """Log changes to member nicknames."""
    embed = discord.Embed(
        title="Nickname Changed",
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )

    embed.set_author(name=after.global_name, icon_url=after.display_avatar.url)
    embed.description = f"**Member:** {after.mention} (`{after}`)"
    embed.add_field(
        name="Before",
        value=before.nick or "*None*",
        inline=True
    )
    embed.add_field(
        name="After",
        value=after.nick or "*None*",
        inline=True
    )

    embed.set_footer(text=f"User ID: {after.id}")
    await client.logging_channels['member_nickname'].send(embed=embed)


client.run(TOKEN)
