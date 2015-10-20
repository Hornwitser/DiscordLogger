import json
import logging

from discord import Client, utils
import pymysql


def command(func):
    func.command = None
    return func


class LoggerBot(Client):
    def __init__(self, config):
        Client.__init__(self)
        self.config = config
        self.commands = []
        for k, v in LoggerBot.__dict__.items():
            if hasattr(v, 'command'):
                self.commands.append(k)

    def on_socket_raw_send(self, msg, binary):
        self.log_msg(True, msg)

    def on_socket_raw_receive(self, msg):
        self.log_msg(False, msg)

    def log_msg(self, is_send, msg):
        raw = str(msg)
        dr = int(is_send)

        backlog = [('', json.loads(raw))]
        while len(backlog):
            n, e = backlog.pop()
            if type(e) == dict:
                backlog.extend([(k, v) for k, v in e.items()])
            elif type(e) == list:
                backlog.extend([('', v) for v in e])
            elif n in ('session_id', 'token'):
                raw = raw.replace(e, '[REDACTED]')

        m = json.loads(raw)
        if 'op' in m and 'd' in m:

            if 's' in m and 't' in m:
                with connection.cursor() as cursor:
                    sql = ("INSERT INTO message (dir, op, s, t, raw) "
                           "VALUES (%s, %s, %s, %s, %s)")
                    cursor.execute(sql, (dr, m['op'], m['s'], m['t'], raw))
            elif 's' in m:
                with connection.cursor() as cursor:
                    sql = ("INSERT INTO message (dir, op, s, raw) "
                           "VALUES (%s, %s, %s, %s)")
                    cursor.execute(sql, (dr, m['op'], m['s'], raw))
            else:
                with connection.cursor() as cursor:
                    sql = ("INSERT INTO message (dir, op, raw) "
                           "VALUES (%s, %s, %s)")
                    cursor.execute(sql, (dr, m['op'], raw))
        else:
            with connection.cursor() as cursor:
                sql = ("INSERT INTO message (dir, raw) VALUES (%s, %s)")
                cursor.execute(sql, (dr, raw))

        connection.commit()

    def get_role(self, member):
        if member.id in self.config['masters']:
            return 'master'
        elif member.id in self.config['admins']:
            return 'admin'
        elif any((r.id in self.config['admin_roles'] for r in member.roles)):
            return 'admin'
        elif member.id in self.config['ignores']:
            return 'ignore'
        else:
            return 'user'

    def on_message(self, msg):
        if msg.channel.is_private: return
        if not msg.content.startswith(self.config['trigger']): return

        line = msg.content[len(self.config['trigger']):]
        if ' ' in line:
            cmd, arg = line.split(' ', 1)
        else:
            cmd, arg = line, None

        if cmd not in self.commands: return
        func = getattr(self, cmd)

        role = self.get_role(msg.author)
        if role == 'master':
            func(msg, arg)

        elif msg.channel.server.id not in config['active_servers']:
            return

        elif (role == 'admin' and cmd in self.config['admin_commands']
              or role == 'user' and cmd in self.config['user_commands']):
            func(msg, arg)

        elif role != 'ignore' and self.config['noisy_deny']:
            self.send_message(msg.channel, "You do not have permission to "
                              "use this command.")

    @command
    def join(self, message, argument):
        """{invite} - Ask LoggerBot to accept an invite."""
        if argument is not None:
            if 'http' not in argument:
                argument = 'http://discord.gg/{}'.format(argument)
            if self.accept_invite(argument):
                self.send_message(message.channel, "Joined server.")
            else:
                self.send_message(message.channel, "Failed to accept invite.")
        else:
            self.send_message(message.channel, "Need invite to join")

    @command
    def leave(self, message, argument):
        """[id] - Leave a server by id. Uses this server if id is not given."""
        if argument is None:
            server_id = message.channel.server.id
        else:
            server_id = argument

        if server_id not in config['protected_servers']:
            server = utils.find(lambda s: s.id == server_id, self.servers)
            if server is not None:
                self.leave_server(server)
            else:
                self.send_message(message.channel, "Can't find server with id "
                                  "{}".format(server_id))
        else:
            self.send_message(message.channel,
                              "Refusing to leave protected server")

    @command
    def help(self, message, argument):
        """- Show this help text."""
        role = self.get_role(message.author)
        if role == 'master':
            commands = self.commands
        elif role == 'admin':
            commands = self.config['admin_commands']
        elif role == 'user':
            commands = self.config['user_commands']

        text = "Available commands:\n"
        for command in sorted(commands):
            text += "{} {}\n".format(command, getattr(self, command).__doc__)
        self.send_message(message.channel, text)


    def add_field(self, field, field_type, channel, argument):
        if argument is None:
            self.send_message(channel, "Error: missing argument")

        elif field_type == 'user':
            users = [u.id for u in argument]
            if len(users):
                self.config[field].update(users)
                names = ', '.join([u.name for u in argument])
                self.send_message(channel, "Added users {}.".format(names))
            else:
                self.send_message(channel, "No users mentioned to add.")

        elif field_type == 'command':
            commands = set(argument.split(' ')).intersection(self.commands)
            if len(commands):
                self.config[field].update(commands)
                cmds = ", ".join(commands)
                self.send_message(channel, "Added commands {}".format(cmds))
            else:
                self.send_message(channel, "No matching commands to add.")

        elif field_type == 'role':
            roles = channel.server.roles
            name = argument.lower()
            matching_roles = [r for r in roles if name in r.name.lower()]
            if len(matching_roles) == 1:
                self.config[field].update([matching_roles[0].id])
                name = matching_roles[0].name
                self.send_message(channel, "Added role {}.".format(name))
            elif len(matching_roles) == 0:
                self.send_message(channel, "No roles matched {}.".format(name))
            else:
                names = ', '.join([r.name for r in matching_roles])
                self.send_message(channel, "Which one? {}.".format(names))

        elif field_type == 'server':
            servers = self.servers
            name = argument.lower()
            matching_servers = [s for s in servers if name in s.name.lower()]
            if len(matching_servers) == 1:
                self.config[field].update([matching_servers[0].id])
                name = matching_servers[0].name
                self.send_message(channel, "Added server {}.".format(name))
            elif len(matching_servers) == 0:
                self.send_message(channel, "No server match {}.".format(name))
            else:
                names = ', '.join([r.name for r in matching_servers])
                self.send_message(channel, "Which one? {}.".format(names))

    def remove_field(self, field, field_type, channel, argument):
        if argument is None:
            self.send_message(channel, "Error: missing argument")

        elif field_type == 'user':
            users = [u.id for u in argument]
            if len(users):
                self.config[field].difference_update(users)
                names = ', '.join([u.name for u in argument])
                self.send_message(channel, "Removed users {}.".format(names))
            else:
                self.send_message(channel, "No users mentioned to remove.")

        elif field_type == 'command':
            commands = set(argument.split(' ')).intersection(self.commands)
            if len(commands):
                self.config[field].difference_update(commands)
                cmds = ", ".join(commands)
                self.send_message(channel, "Removed commands {}.".format(cmds))
            else:
                self.send_message(channel, "No matching commands to remove.")

        elif field_type == 'role':
            roles = channel.server.roles
            name = argument.lower()
            matching_roles = [r for r in roles if name in r.name.lower()]
            if len(matching_roles) == 1:
                self.config[field].difference_update([matching_roles[0].id])
                name = matching_roles[0].name
                self.send_message(channel, "Removed role {}.".format(name))
            elif len(matching_roles) == 0:
                self.send_message(channel, "No roles matched {}.".format(name))
            else:
                names = ', '.join([r.name for r in matching_roles])
                self.send_message(channel, "Which one? {}".format(names))

        elif field_type == 'server':
            servers = self.servers
            name = argument.lower()
            matching_servers = [s for s in servers if name in s.name.lower()]
            if len(matching_servers) == 1:
                self.config[field].difference_update([matching_servers[0].id])
                name = matching_servers[0].name
                self.send_message(channel, "Removed server {}.".format(name))
            elif len(matching_servers) == 0:
                self.send_message(channel, "No server match {}.".format(name))
            else:
                names = ', '.join([r.name for r in matching_servers])
                self.send_message(channel, "Which one? {}.".format(names))

    @command
    def add_admin(self, message, argument):
        """{user} ... - Add mentioned users to list of admins."""
        self.add_field('admins', 'user', message.channel, message.mentions)

    @command
    def remove_admin(self, message, argument):
        """{user} ... - Remove mentioned users from list of admins."""
        self.remove_field('admins', 'user', message.channel, message.mentions)

    @command
    def add_admin_role(self, message, argument):
        """{role} - Add role to admin role list."""
        self.add_field('admin_roles', 'role', message.channel, argument)

    @command
    def remove_admin_role(self, message, argument):
        """{role} - Remove role from admin role list."""
        self.remove_field('admin_roles', 'role', message.channel, argument)

    @command
    def add_user_command(self, message, argument):
        """{command} ... - Add command(s) to user command list."""
        self.add_field('user_commands', 'command', message.channel, argument)

    @command
    def remove_user_command(self, message, argument):
        """{command} ... - Remove command(s) from user command list."""
        self.remove_field('user_commands', 'command',
                          message.channel, argument)

    @command
    def add_admin_command(self, message, argument):
        """{command} ... - Add command(s) to admin command list."""
        self.add_field('admin_commands', 'command', message.channel, argument)

    @command
    def remove_admin_command(self, message, argument):
        """{command} ... - Remove command(s) from admin command list."""
        self.remove_field('admin_commands', 'command',
                          message.channel, argument)

    @command
    def listen_on(self, message, argument):
        """{server name} - Start listening for commands on server"""
        self.add_field('active_servers', 'server', message.channel, argument)

    @command
    def ignore_server(self, message, argument):
        """{server name} - Stop listening for commands on server"""
        self.remove_field('active_servers', 'server',
                          message.channel, argument)


    @command
    def debug_conf(self, message, argument):
        lines = ['    {!r}: {!r},'.format(k, self.config[k]) for k in sorted(self.config)]
        print('\n'.join(['# LoggerBot config', '{']+lines+['}']))

    @command
    def debug(self, message, argument):
        """{python expression} - Evaluate an arbitrary python expression"""
        try:
            self.send_message(message.channel, eval(argument))
        except Exception as e:
            self.send_message(message.channel,
                              '{} {}'.format(type(e).__name__, e))


def write_config(config):
    config_file = open('config.py', 'w')
    lines = ['    {!r}: {!r},'.format(k, config[k]) for k in sorted(config)]
    config_file.write('\n'.join(['# LoggerBot config', '{']+lines+['}']))
    config_file.close()

if __name__ == '__main__':
    global connection
    config = eval(open('config.py').read())
    logging.basicConfig(level=logging.INFO)
    connection = pymysql.connect(host=config['db_host'],
                                 user=config['db_user'],
                                 password=config['db_password'],
                                 db=config['db_schema'],
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)

    bot = LoggerBot(config)
    bot.login(config['bot_user'], config['bot_password'])
    try:
        bot.run()
    finally:
        write_config(config)
