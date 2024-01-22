import configparser
import datetime
import discord
import hashlib
import json
import os
import signal
import re
import requests
import subprocess
import tempfile
import time



TOKEN = None
GUILD_NAME = None             # Server's name
CHANNELS_NAME = []            # Server's channels
PASSWORD = None
SHARED_FOLDER = None          # Shared files storage folder path
USERS_FILE = None             # users.txt path
LOG_FILE = None               # log.txt path
LOG_LIMIT = None              # Max number of lines to register in log
ENABLE_ROOT = False
FORBIDDEN_COMMANDS = []       # Non working/disabled commands

CLIENT = discord.Client(intents=discord.Intents.all())     # Discord client
IN_GUILD = False              # Is bot running in configured server?
LOG_LINES = 0                 # Current lines of log.txt
COMMANDS_QUEUE = {}           # Used for updating and upgrading the system
AUTHENTIFIED_USERS = set()    # Users allowed to send commands
CUSTOM_COMMANDS = []          # Bot custom commands
FORBIDDEN_COMMANDS = []       # Non working commands
CURRENT_PROCESS = None        # Current process being executed

UPDATE_COMMAND = None         # Command used to update system
UPGRADE_COMMAND = None        # Command used to upgrade system
INSTALL_COMMAND = None        # Command used to install a package
REMOVE_COMMAND = None         # Command used to remove a package


def load_config(config_file):
    global TOKEN, GUILD_NAME, CHANNELS_NAME, PASSWORD, SHARED_FOLDER, \
           USERS_FILE, LOG_FILE, LOG_LIMIT, ENABLE_ROOT, FORBIDDEN_COMMANDS, \
           UPDATE_COMMAND, UPGRADE_COMMAND, INSTALL_COMMAND, REMOVE_COMMAND
    config = configparser.ConfigParser()
    config.read(config_file)
    TOKEN = config.get('GENERAL', 'token')
    GUILD_NAME = config.get('GENERAL', 'guild_name')
    CHANNELS_NAME = json.loads(config.get('GENERAL', 'channels_name'))
    PASSWORD = config.get('GENERAL', 'password')
    SHARED_FOLDER = config.get('FILES', 'shared_folder')
    USERS_FILE = config.get('FILES', 'users_file')
    LOG_FILE = config.get('FILES', 'log_file')
    LOG_LIMIT = int(config.get('FILES', 'log_limit'))
    ENABLE_ROOT = config.getboolean('PERMISSIONS', 'enable_root')
    FORBIDDEN_COMMANDS = json.loads(config.get('USAGE', 'forbidden_commands'))



def initialize():
    """
    Read config and create configured files and folders.
    """
    global COMMANDS_QUEUE, CUSTOM_COMMANDS, CLIENT

    config_path = os.getcwd() + "/config.txt"
    load_config(config_path)
    error, error_msg = check_config()

    CUSTOM_COMMANDS = ["/update", "/upgrade", "/install",
                       "/uninstall", "/forbidden", "/help",
                       "/reload", "/stop", "/getfile"]
    COMMANDS_QUEUE = {
                      'update': set(),
                      'upgrade': set(),
                      'install': {},
                      'uninstall': {}
    }
    if not error:
        os.makedirs(SHARED_FOLDER, exist_ok=True)
        f1 = open(LOG_FILE, "a+")
        f1.close
        f2 = open(USERS_FILE, "a+")
        f2.close

        with open(LOG_FILE) as f:
            LOG_LINES = sum(1 for _ in f)
    else:
        print(error_msg)
        exit()


def check_config():
    global TOKEN, GUILD_NAME, CHANNELS_NAME, PASSWORD, SHARED_FOLDER, \
           USERS_FILE, LOG_FILE, LOG_LIMIT, ENABLE_ROOT, FORBIDDEN_COMMANDS, \
           UPDATE_COMMAND, UPGRADE_COMMAND, INSTALL_COMMAND, REMOVE_COMMAND

    error = False
    error_msg = "Config file not properly filled, errors:"
    if not CHANNELS_NAME or len(CHANNELS_NAME) <= 0:
            error = True
            error_msg += "\n- Channel name field is empty."
    if not PASSWORD or len(PASSWORD) <= 0:
            error = True
            error_msg += "\n- Password field is empty."
    if not SHARED_FOLDER or len(SHARED_FOLDER) <= 0:
        error = True
        error_msg += "\n- Shared folder field is empty."
    if "./" in SHARED_FOLDER:
        error = True
        error_msg += "\n- Shared folder path is relative."
    if not USERS_FILE or len(USERS_FILE) <= 0:
        error = True
        error_msg += "\n- Users file field is empty."
    if "./" in USERS_FILE:
        error = True
        error_msg += "\n- Users file field is relative."
    if not LOG_FILE or len(LOG_FILE) <= 0:
        error = True
        error_msg += "\n- Log file field is empty."
    if "./" in LOG_FILE:
        error = True
        error_msg += "\n- Log file path is relative."
    if not LOG_LIMIT or LOG_LIMIT < 0:
        error = True
        error_msg += "\n- Log limit wrong value."
    if type(ENABLE_ROOT) is not bool:
        error = True
        error_msg += "\n- Enable root field is empty."
    if not FORBIDDEN_COMMANDS:
        FORBIDDEN_COMMANDS = []
    return error, error_msg


def in_guild(func):
    """
    Check whether bot is running in configured server
    """
    def wrapper(*args, **kwargs):
        if IN_GUILD:
            return func(*args, **kwargs)
        return wrapper


def in_channel(message):
    """
    Check whether message comes from configured channels
    """
    return True if str(message.channel) in CHANNELS_NAME else False


def encrypt(id):
    """
    Cipher user id using SHA256
    """
    m = hashlib.sha256()
    m.update(str(id).encode())
    return m.hexdigest()


def register_user(user_id):
    """
    Add user to users.txt
    """
    encrypted_user = encrypt(user_id)
    f = open(USERS_FILE, "a+")
    content = f.readlines()
    content = [x.strip() for x in content]
    if encrypted_user not in content:
        f.write(str(encrypted_user) + "\n")
    f.close()


def check_user(id):
    """
    Check if user ID is registered in users.txt
    """
    global AUTHENTIFIED_USERS

    encrypted_id = encrypt(id)
    check = False
    with open(USERS_FILE) as f:
        content = f.readlines()
        content = [x.strip() for x in content]
        if encrypted_id in content:
            check = True
    return check


def allow_user(user_id):
    """
    Add user to authentified users set
    """
    global AUTHENTIFIED_USERS

    AUTHENTIFIED_USERS.add(user_id)


def register_log(message):
    """
    Register message in log.txt
    """
    global LOG_LIMIT, LOG_FILE, LOG_LINES
    LOG_LINES += 1
    with open(LOG_FILE, 'a+') as f:
        now = datetime.datetime.now().strftime("%m-%d-%y %H:%M:%S ")
        f.write(now + "[" + str(message.author.name) + " (" +
                str(message.author.id) + ")]: " + str(message.content) + "\n")
    if LOG_LIMIT > 0 and LOG_LINES > LOG_LIMIT:
        with open(LOG_FILE) as f:
            lines = f.read().splitlines(True)
        with open(LOG_FILE, 'w+') as f:
            f.writelines(lines[abs(LOG_LINES - LOG_LIMIT):])


async def ask_password(message):
    await message.author.create_dm()
    await message.author.dm_channel.send("Enter sudo password.")


def check_password(passwd):
    com = f"sudo -K | echo {passwd} | sudo -S echo 1"
    proc = subprocess.Popen(com, shell=True, stdin=None,
                            stdout=subprocess.PIPE, executable="/bin/bash")
    for line in iter(proc.stdout.readline, b''):
        return True
    else:
        return False

async def show_forbidden_commands(channel):
    res = ""
    for element in FORBIDDEN_COMMANDS:
        res += element + ", "
    await channel.send(res[:-2])


async def stop_proccess(message):    # Send ctrl+c to current process
    global CURRENT_PROCESS

    if CURRENT_PROCESS:
        CURRENT_PROCESS.send_signal(signal.SIGINT)
        await message.channel.send("Ctrl + c sent.")
    else:
        await message.channel.send("There is no process running.")


@CLIENT.event
async def on_ready():
    """
    Search for configured server through discord
    """
    global IN_GUILD

    guild = discord.utils.get(CLIENT.guilds, name=GUILD_NAME)
    if guild:
        IN_GUILD = True
        print(f"Server {GUILD_NAME} found! running...")
        await send_welcome_msg(guild)
        return
    print(f"Server {GUILD_NAME} not found...")
    exit()


async def send_welcome_msg(guild):
    """
    Send welcome message to first configured channel
    """
    global CUSTOM_COMMANDS, CHANNELS_NAME, __version__, SHARED_FOLDER

    msg_zero = f"---- DiscordShellBot version: {__version__} ----"
    msg_one = "\n\nThis bot allows " + \
              "you to remotely control a computer through shell commands."

    msg_two = "\nList of avaliable commands: " + \
              "\n    **· /stop**: Send CTRL+C signal to running process." + \
              "\n    **· /getfile**: Download the given file (absolute path)."
    msg_three = "\nSent files to the computer will be saved in" + \
                f" configured shared folder: *{SHARED_FOLDER}*"
    msg_four = "\nYou can download files by using getfile + absolute " + \
               "path (*e.g. getfile /home/user/Desktop/file.txt*)."
    channel = discord.utils.get(guild.channels, name=CHANNELS_NAME[0],
                                type=discord.ChannelType.text)
    welcome_msg = msg_zero + msg_one + msg_two + msg_three + msg_four
    await channel.send(welcome_msg)


async def send_command(command, channel):
    global CURRENT_PROCESS

    """
    Send an empty message to user and edit it with command output
    """
    output = "ㅤ"    # Invisible character
    msg_output = await channel.send(output)
    output = ""
    n_lines = 0
    try:
        CURRENT_PROCESS = subprocess.Popen(command, shell=True, stdin=None,
                                           stdout=subprocess.PIPE,
                                           executable="/bin/bash")
        for line in iter(CURRENT_PROCESS.stdout.readline, b''):
            decoded = line.decode('windows-1252').strip()
            if n_lines > 25:
                msg_output = await channel.send(output)
                n_lines = 0
                output = ""
            if len(re.sub('[^A-Za-z0-9]+', '', decoded)) <= 0:
                # Empty message that raises api 400 error
                # Send special blank character
                output += "\n"
                await msg_output.edit(content=output)
            else:
                try:
                    output += line.decode('utf-8')
                    await msg_output.edit(content=output)
                except Exception as e:
                    msg_error = str(e)
                    await channel.send(msg_error)
                    error_code = str(e).split()[str(e).split().index('code:')
                                                + 1][:-2]
            n_lines += 1
        error = CURRENT_PROCESS.communicate()
        CURRENT_PROCESS.wait()
    except Exception as e:
        error = "Error: Command not found"
        await msg_output.edit(content=error)
    code = CURRENT_PROCESS.returncode
    CURRENT_PROCESS = None
    return code, msg_output


@in_guild
@CLIENT.event
async def on_message(message):
    """
    Send command to computer and return the output
    """
    global USERS_FILELOGIN, VERSION, FORBIDDEN_COMMANDS, ENABLE_ROOT, \
        AUTHENTIFIED_USERS, COMMANDS_QUEUE

    if message.author == CLIENT.user:  # Ignore self messages
        return

    if in_channel(message):
        register_log(message)

    # Register access password
    if message.author.id not in AUTHENTIFIED_USERS:
        if message.content == PASSWORD:
            if isinstance(message.channel, discord.channel.DMChannel):
                register_user(message.author.id)    # Register in users.txt
                allow_user(message.author.id)    # Grant access to user
                response = "Logged in, you can use commands now."
                await message.author.dm_channel.send(response)
            return
        if not check_user(message.author.id) and in_channel(message):
            await message.author.create_dm()
            response = "Please log in, insert a valid password."
            await message.author.dm_channel.send(response)
            return

    if not in_channel(message):
        return

    # File sent
    if len(message.attachments) > 0:
        file_path = SHARED_FOLDER + message.attachments[0].filename
        r = requests.get(message.attachments[0].url)
        with open(file_path, 'wb') as file:
            file.write(r.content)
        await message.channel.send(f"File saved as {file_path}")
        return


    if message.content[0:8] == "/getfile":
        file_path = os.path.join(message.content[8:].strip())
        if os.path.isfile(file_path):
            file = discord.File(file_path)
            await message.channel.send(files=[file])
        else:
            await message.channel.send("File doesn't exists.")

    # else:    # Any other command
    #     try:
    #         if in_channel(message):
    #             await send_command(message.content, message.channel)
    #     except Exception as e:
    #         error = "Error: Command not found"
    #         await message.channel.send(error, e)
    return


def main():
    global CLIENT, TOKEN

    initialize()
    CLIENT.run(TOKEN)

if __name__ == "__main__":
    main()
