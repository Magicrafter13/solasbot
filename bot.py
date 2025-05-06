#!/usr/bin/python3
"""Bot for various administrative duties in the Solas Council."""

import asyncio
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from os import environ
from typing import Optional

import discord
from discord import app_commands, Client, Guild, Intents, Interaction, Member

from config import (
    CHANNEL_CLEAR_WHITELIST,
    LOGGING_SETTINGS,
    MAX_ALLOWED_BAN_ROLE_ID as ban_role_id,
    PRIMARY_GUILD,
    STAFF_ROLE_ID as role_id,
    TOKEN,
)

logging.basicConfig(level=logging.INFO)
sys.stdout.reconfigure(line_buffering=True)

# Config

DRY_RUN = environ.get('DRY_RUN', 'False').lower() == 'true'
LOGGING_GUILD, LOGGING_CHANNEL = LOGGING_SETTINGS

# Discord Stuff

intents = Intents.default()
#intents.message_content = True
intents.members = True
#intents.reactions = True
client = Client(intents=intents)
tree = app_commands.CommandTree(client)

client.primary_guild: Guild = None
client.logging_guild: Guild = None

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

async def try_authorization(interaction: Interaction, user: Optional[Member]=None) -> bool:
    """Check if user is authorized to run command, inform them if they aren't."""
    # Check that they are an administrator/moderator
    if not role_id in [role.id for role in interaction.user.roles]:
        await interaction.response.send_message(
            'You are not authorized to use this command!',
            ephemeral=True)
        return False
    # If the interaction involves another user, make sure that they are within the bot's
    # jurisdiction
    if user:
        guild_roles = [role.id for role in interaction.guild.roles]
        if guild_roles.index(user.roles[-1].id) > guild_roles.index(ban_role_id):
            await interaction.response.send_message(
                f'You are not allowed to run `/{interaction.command.name}` on this user due to their roles.',
                ephemeral=True)
            return False
    return True

async def send_dm(user: Member, message: str) -> bool:
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

async def log_action(action: str, user: Member, info: Optional[str]=''):
    """Log a bot action, with optional additional information."""
    if info != '':
        info = f'\n\n{info}'
    await client.logging_channel.send(f'action: `{action}`\nstaff member: <@{user.id}>{info}')

# Bot commands

@tree.command(name='ban', description='6 month ban')
@app_commands.describe(user='Username to ban.', reason='Optional reason for banning.')
async def ban(interaction: Interaction, user: Member, reason: Optional[str]='none given'):
    """Add user to ban database, and then bans them."""
    if await try_authorization(interaction, user) is False:
        return

    # DM banee
    if not await send_dm(
        user,
        f'You have receive a 6-month ban from The Solas Council.\nGiven reason:\n> {reason}'
    ):
        await interaction.channel.send(f'Failed to DM {user}, check logs.')

    # Add to database
    CURSOR.execute(
        '''
            INSERT INTO bans
            VALUES (?, date('now'))
            ON CONFLICT (user) DO
                UPDATE SET date = date('now');
        ''',
        (user.id,))
    CONN.commit()

    # Ban user
    if DRY_RUN:
        return
    try:
        await interaction.guild.ban(user, reason=reason)
    except discord.Forbidden:
        return await interaction.response.send_message(f'Lacking permissions to ban {user}!')

    await log_action('ban (6 month)', interaction.user, f'user banned: <@{user.id}>\nreason:\n> {reason}')
    return await interaction.response.send_message(
        f'Banned {user} (`{user.id}`) with reason `{reason}`.')

@tree.command(name='kick', description='Kick someone from the server.')
@app_commands.describe(user='Member to kick.', reason='Optional reason for kicking.')
async def kick(interaction: Interaction, user: Member, reason: Optional[str]='none given'):
    """Kick user, and tell them why."""
    if await try_authorization(interaction, user) is False:
        return

    # DM banee
    if not await send_dm(
        user,
        f'You have been kicked from The Solas Council.\nGiven reason:\n> {reason}'
    ):
        await interaction.channel.send(f'Failed to DM {user}, check logs.')

    # Kick user
    if DRY_RUN:
        return
    try:
        interaction.guild.kick(user, reason=reason)
    except discord.Forbidden:
        return await interaction.response.send_message(f'Lacking permissions to kick {user}!')

    await log_action('kick', interaction.user, f'user kicked: <@{user.id}>\nreason:\n> {reason}')
    return await interaction.response.send_message(
        f'Kicked {user} (`{user.id}`) with reason `{reason}`.')

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
    user: Member,
    time: str,
    reason: Optional[str]='none given'
):
    """Timeout user, and tell them why."""
    if await try_authorization(interaction, user) is False:
        return

    # DM rascal
    if not await send_dm(
        user,
        f'You have been timed out in The Solas Council.\nGiven reason:\n> {reason}'
    ):
        await interaction.channel.send(f'Failed to DM {user}, check logs.')

    # Timeout user
    try:
        await user.timeout(SOLAS_TIMEOUTS[time], reason=reason)
    except discord.Forbidden:
        return await interaction.response.send_message(f'Lacking permissions to timeout {user}!')

    await log_action('timeout', interaction.user, f'user timed out: <@{user.id}>\nlength of time: {time}\nreason:\n> {reason}')
    return await interaction.response.send_message(
        f'Timed out {user} (`{user.id}`) for {time} with reason `{reason}`.')

@tree.command(name='clear', description='Delete all the messages in the current channel.')
async def clear(interaction: Interaction):
    """Delete every message in the channel, if it is in the whitelist."""
    if await try_authorization(interaction) is False:
        return

    if not interaction.channel_id in CHANNEL_CLEAR_WHITELIST:
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

    await log_action('channel clear', interaction.user, f'channel: https://discord.com/channels/{PRIMARY_GUILD}/{interaction.channel_id}')
    return await interaction.followup.send('Done!', ephemeral=True)

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
            WHERE date < datetime('now', '-6 months');
        ''')
        pardons = CURSOR.fetchall()
        for user_id, _ in pardons:
            logging.info('Unbanning %s...', user_id)
            try:
                await client.primary_guild.unban(
                    await client.fetch_user(user_id),
                    reason='6-month ban expired')
            except discord.NotFound:
                logging.warning("User wasn't banned!")
            CURSOR.execute('DELETE FROM bans WHERE user = ?;', (user_id,))
            CONN.commit()


@client.event
async def on_ready():
    """Initialize bot data and tasks."""
    logging.info('Logged in as %s.', client.user)
    client.primary_guild = await client.fetch_guild(PRIMARY_GUILD)
    client.logging_guild = await client.fetch_guild(LOGGING_GUILD)
    client.logging_channel = await client.logging_guild.fetch_channel(LOGGING_CHANNEL)
    client.loop.create_task(unban_users())
    await asyncio.sleep(5)
    await tree.sync()

client.run(TOKEN)
