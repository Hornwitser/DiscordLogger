# Logger bot configuration.
{
    # These messages will dissapear after the bot has been run
    # Most of these settings can be changed from within the bot
    # itself.  See the help command.
    'active_servers': set(),
    'admin_commands': {'help', 'ignore_server', 'listen_on', 'leave', 'join'},
    'admin_roles': set(),
    'admins': set(),

    # Discord user for the bot.
    'bot_user': 'logger@example.com',
    'bot_password': 'Password for Discord user'

    # MySQL database connection.
    'db_host': 'localhost',
    'db_user': 'logger',
    'db_password': 'Password for database user',
    'db_schema': 'discord',

    'ignores': set(),

    # Set of user ids that are masters of bot, and can do any command.
    'masters': {'your-user-id-number'},
    'noisy_deny': True,
    'protected_servers': set(),

    # Character used to triggering commands in the bot.  Setting it
    # to '!', means commands start with an ! character (e.g, !help).
    'trigger': '!',

    'user_commands': {'help', 'leave', 'join'},
}
