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
    'member_join': (1234567890123456789, 1234567890123456789),  # members joining the primary guild
    'member_leave': (1234567890123456789, 1234567890123456789),  # members leaving the primary guild
    'message_edit': (1234567890123456789, 1234567890123456789),  # message edited in primary guild
    'messages_delete': (1234567890123456789, 1234567890123456789),  # message deleted in primary guild
    'member_role': (1234567890123456789, 1234567890123456789),  # member roles modified in primary guild
    'member_nickname': (1234567890123456789, 1234567890123456789),  # member nickname modified in primary guild
    'member_avatar': (1234567890123456789, 1234567890123456789),  # member avatar modified in primary guild
    'server': (1234567890123456789, 1234567890123456789),  # primary guild updates (channels, roles, permissions, etc)
}

EXTRA_GUILDS = [9826784289674238479]  # list[int] - any other guilds where user bans/kicks/timeouts should be applied
