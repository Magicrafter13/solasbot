#!/usr/bin/python3
"""Bot for various administrative duties in the Solas Council."""

import asyncio
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from typing import Optional

from discord import app_commands, Client, Forbidden, Guild, Intents, Interaction, Member, NotFound

from config import MAX_ALLOWED_BAN_ROLE_ID as ban_role_id, STAFF_ROLE_ID as role_id, TOKEN

logging.basicConfig(level=logging.INFO)
sys.stdout.reconfigure(line_buffering=True)

intents = Intents.default()
#intents.message_content = True
intents.members = True
#intents.reactions = True
client = Client(intents=intents)
tree = app_commands.CommandTree(client)

client.solas: Guild = None

# Connect to local database
CONN = sqlite3.connect('users.db')
CURSOR = CONN.cursor()
# Create tables if they don't exist
CURSOR.execute('''
    CREATE TABLE IF NOT EXISTS bans (
        user INT NOT NULL PRIMARY KEY,
        date TIMESTAMP
    );''')

@tree.command(name='ban', description='6 month ban')
@app_commands.describe(user='Username to ban.', reason='Optional reason for banning.')
async def ban(interaction: Interaction, user: Member, reason: Optional[str]='none given'):
    """Add user to ban database, and then bans them."""
    # Make sure user is authorized to run command
    if not role_id in [role.id for role in interaction.user.roles]:
        return await interaction.response.send_message(
            'You are not authorized to use this command!',
            ephemeral=True)
    guild_roles = [role.id for role in interaction.guild.roles]
    if guild_roles.index(user.roles[-1].id) > guild_roles.index(ban_role_id):
        return await interaction.response.send_message(
            'You are not allowed to ban this user due to their roles.',
            ephemeral=True)

    dm = user.dm_channel
    if not user.dm_channel:
        dm = await user.create_dm()

    await dm.send(
        f'You have receive a 6-month ban from The Solas Council.\nGiven reason:\n> {reason}')

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
    try:
        await interaction.guild.ban(user, reason=reason)
    except Forbidden:
        return await interaction.response.send_message(f'Lacking permissions to ban {user}!')

    return await interaction.response.send_message(
        f'Banned {user} (`{user.id}`) with reason `{reason}`.')

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
                await client.solas.unban(
                    await client.fetch_user(user_id),
                    reason='6-month ban expired')
            except NotFound:
                logging.warning("User wasn't banned!")
            CURSOR.execute('DELETE FROM bans WHERE user = ?;', (user_id,))
            CONN.commit()


@client.event
async def on_ready():
    """Initialize bot data and tasks."""
    logging.info('Logged in as %s.', client.user)
    client.solas = client.get_guild(918486134164692992)
    client.loop.create_task(unban_users())
    await asyncio.sleep(5)
    await tree.sync()

client.run(TOKEN)
