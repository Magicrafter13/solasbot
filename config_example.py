"""Bot configuration."""

TOKEN = 'SLKFdjkjsfdLSKDF.fskjfSKFJflSJF_ksjfdlLs.sdfkjslkfjsLSKDkd.d.sKJSlsd_jAL'  # str - bot token

PRIMARY_GUILD = {
    'id': 1234567890123456789,  # int - where the bot operates
    'staff_role_id': 9128642689240684734,  #  int - role ID in the primary guild
    'max_bannable_role_id': 9813589165928698248,  # int - role ID in the primary guild
    'clear_channel_whitelist': [1234567890123456789],  # list[int] - channel IDs in the primary guild
}

# tuple[int,int] - where the first value is the guild ID and the second value is the channel ID
LOGGING = {
    'mod_actions': (1234567890123456789, 1234567890123456789),  # any moderation actions taken by the bot
    'join_leave': (1234567890123456789, 1234567890123456789),  # members joining or leaving the primary guild
    'messages': (1234567890123456789, 1234567890123456789),  # primary guild message updates (edits and deletions)
    'members': (1234567890123456789, 1234567890123456789),  # primary guild member updates (nicknames, avatars, etc)
    'server': (1234567890123456789, 1234567890123456789),  # primary guild updates (channels, roles, permissions, etc)
}

EXTRA_GUILDS = [9826784289674238479]  # list[int] - any other guilds where user bans/kicks/timeouts should be applied
