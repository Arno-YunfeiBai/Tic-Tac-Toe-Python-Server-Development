import sys
import socket
import re
import os
import json
import multiprocessing
import bcrypt

from Room import Room


def main(args: list[str]) -> None:
    """
    Main function to start the game server. Reads the server configuration, initializes 
    the multiprocessing manager and sets up the server socket to accept client connections.

    Args:
        args (list): A list containing the command line arguments, where the first argument 
                     should be the path to the server config file.

    Returns:
        None: The server continuously runs, accepting and handling client connections.
    """
    if len(args) != 1:
        print("Error: Expecting 1 argument: <server config path>.", file=sys.stderr)
        sys.exit(0)
    server_config_path = args[0]
    expanded_config_path = os.path.expanduser(server_config_path)

    if not os.path.exists(expanded_config_path):
        print(f"Error: {expanded_config_path} doesn't exist.", file=sys.stderr)
        sys.exit(0)

    try:
        with open(expanded_config_path, 'r', encoding='utf-8') as config_file:
            config = json.load(config_file)
    except json.JSONDecodeError:
        print(f"Error: {expanded_config_path} is not in a valid JSON format.", file=sys.stderr)
        sys.exit(1)

    config_file.close()

    manager = multiprocessing.Manager()
    clients = manager.dict()
    authenticated_clients = manager.dict()
    users = manager.dict()
    rooms = manager.dict()

    required_keys = ['port', 'userDatabase']
    missing_keys = [key for key in required_keys if key not in config]

    if missing_keys:
        missing_keys.sort()
        missing_key_list = ", ".join(missing_keys)
        print(f"Error: {expanded_config_path} missing key(s): {missing_key_list}", file=sys.stderr)
        sys.exit(0)

    port = config['port']
    if not 1024 <= port <= 65535:
        print("Error: port number out of range.", file=sys.stderr)
        sys.exit(0)
    user_database_path = config['userDatabase']
    users_from_the_file = read_user_database(user_database_path)

    for user in users_from_the_file:
        users[user['username']] = user['password'].encode('utf-8')

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('', port))
    server_socket.listen(5)
    print(f"Server is listening on port {port}...", flush=True)
    try:
        while True:
            client_socket, client_address = server_socket.accept()
            print(f"Connection established with {client_address}", flush=True)
            process = multiprocessing.Process(
                target=handle_client,
                args=(client_socket,
                    client_address,
                    clients,
                    authenticated_clients,
                    users,
                    rooms,
                    user_database_path
                )
            )
            process.start()

    finally:
        for client in clients:
            client.close()
        server_socket.close()
        print("Server shut down.", flush=True)

def handle_client(
    client_socket,
    client_address,
    clients,
    authenticated_clients,
    users,
    rooms,
    user_database_path
):
    """
    Handles client communication by receiving messages and processing them. Manages client 
    disconnections and updates the client and room state accordingly.

    Args:
        client_socket (socket): The client's socket for communication.
        client_address (tuple): The client's address (IP, port).
        clients (dict): Dictionary tracking client sockets and associated rooms.
        authenticated_clients (dict): Dictionary of authenticated clients and their usernames.
        users (dict): Dictionary of registered users with hashed passwords.
        rooms (dict): Dictionary of active game rooms.
        user_database_path (str): Path to the user database JSON file.

    Returns:
        None: Processes the client's messages and updates the game state.
    """
    clients[client_socket] = None
    try:
        while True:
            data = client_socket.recv(8192)
            if not data:
                print(f"client:{client_address} has quit", flush=True)
                break
            message = data.decode('utf-8').strip()
            handle_message(
                client_socket,
                message,
                authenticated_clients,
                users,
                rooms,
                clients,
                user_database_path
            )
    except ConnectionResetError:
        print(f"client:{client_address} has quit", flush=True)
    except ConnectionAbortedError:
        print(f"client:{client_address} has quit", flush=True)
    finally:
        new_authenticated_clients = {
            k: v
            for k, v in authenticated_clients.items()
            if not is_same_socket(k, client_socket)
        }
        authenticated_clients.clear()
        authenticated_clients.update(new_authenticated_clients)

        #if a player quit when he is currently in a game
        room_need_to_be_closed = None
        for key,value in clients.items():
            if is_same_socket(key, client_socket):
                room_need_to_be_closed = value

        if (
            not room_need_to_be_closed is None
            and not rooms[room_need_to_be_closed].able_to_add_player()
            and rooms[room_need_to_be_closed].in_room_as_a_player(client_socket)
        ) :
            winner = rooms[room_need_to_be_closed].get_another_player(client_socket)
            for key, value in authenticated_clients.items():
                if is_same_socket(key, winner):
                    winner_name = value
            gameend_forfeit_message = (
                "GAMEEND:"
                + rooms[room_need_to_be_closed].get_matrix_in_string()
                + ":2:"
                + winner_name
            )
            rooms[room_need_to_be_closed].get_another_player(client_socket).sendall(
                gameend_forfeit_message.encode('utf-8')
            )
            rooms[room_need_to_be_closed].send_to_all_viewers(gameend_forfeit_message)

            new_clients = {
                k: v
                for k, v in clients.items()
                if (
                    not is_same_socket(k, client_socket))
                    and (not is_same_socket(
                        k, rooms[room_need_to_be_closed].get_another_player(client_socket)
                    )
                )
            }
            new_clients[client_socket] = None
            new_clients[rooms[room_need_to_be_closed].get_another_player(client_socket)] = None
            clients.clear()
            clients.update(new_clients)

            my_dict = {k: v for k, v in rooms.items() if k != room_need_to_be_closed}
            rooms.clear()
            rooms.update(my_dict)
        #if a player quit a room before another player join in.
        elif (
            not room_need_to_be_closed is None
            and rooms[room_need_to_be_closed].in_room_as_a_player(client_socket)
        ) :
            rooms[room_need_to_be_closed].send_to_all_viewers("Room owner has quited.")
            my_dict = {k: v for k, v in rooms.items() if k != room_need_to_be_closed}
            rooms.clear()
            rooms.update(my_dict)

        new_clients = {k: v for k, v in clients.items() if not is_same_socket(k, client_socket)}
        clients.clear()
        clients.update(new_clients)

        client_socket.close()

def handle_message(
        sender_socket,
        message,
        authenticated_clients,
        users, rooms,
        clients,
        user_database_path
):
    """
    Processes messages received from clients and routes them to the appropriate handler 
    based on the message type (LOGIN, REGISTER, ROOMLIST, etc.).

    Args:
        sender_socket (socket): The client's socket for sending responses.
        message (str): The message received from the client.
        authenticated_clients (dict): Dictionary of authenticated clients and their usernames.
        users (dict): Dictionary of registered users with hashed passwords.
        rooms (dict): Dictionary of active game rooms.
        clients (dict): Dictionary tracking client sockets and associated rooms.
        user_database_path (str): Path to the user database JSON file.

    Returns:
        None: Routes the message to the appropriate function (login, register, etc.).
    """
    splited_message = message.split(":")
    if splited_message[0] == "LOGIN":
        login(splited_message[1:], sender_socket, authenticated_clients, users)
    elif splited_message[0] == "REGISTER":
        register(splited_message[1:], sender_socket, users, user_database_path)
    else:
        if not check_authorizations(sender_socket, authenticated_clients):
            sender_socket.sendall("BADAUTH".encode('utf-8'))
        else:
            if splited_message[0] == "ROOMLIST":
                room_list(splited_message[1:], sender_socket, rooms)
            elif splited_message[0] == "CREATE":
                create_room(splited_message[1:], sender_socket, rooms,clients)
            elif splited_message[0] == "JOIN":
                join_room(splited_message[1:], sender_socket, rooms, clients, authenticated_clients)
            else:
                roomname = None
                for room in rooms.keys():
                    if rooms[room].in_room_as_a_player(sender_socket):
                        roomname = room
                if roomname is None:
                    sender_socket.sendall("NOROOM".encode('utf-8'))
                else:
                    user_type = "VIEWER"
                    if rooms[roomname].in_room_as_a_player(sender_socket):
                        user_type = "PLAYER"
                    if user_type != "VIEWER":
                        while (
                            not rooms[roomname].get_has_began()
                            or not is_same_socket(
                                rooms[roomname].get_current_player(),
                                sender_socket
                            )
                        ):
                            if (
                                rooms[roomname].get_has_began()
                                and is_same_socket(
                                    rooms[roomname].get_current_player(),
                                    sender_socket
                                )
                            ):
                                break
                        if splited_message[0] == "PLACE":
                            place(
                                splited_message,
                                sender_socket,
                                roomname, rooms,
                                clients,
                                authenticated_clients
                            )
                        elif splited_message[0] == "FORFEIT":
                            forfeit(
                                sender_socket,
                                roomname,
                                rooms,
                                clients,
                                authenticated_clients
                            )

def forfeit(sender_socket, roomname, rooms, clients, authenticated_clients):
    """
    Handles a player forfeiting the game, declares the opponent as the winner, and updates 
    the game state for both players and viewers. It also cleans up the room and client lists.

    Args:
        sender_socket (socket): The client's socket representing the forfeiting player.
        roomname (str): The name of the room in which the forfeit is happening.
        rooms (dict): Dictionary of active game rooms.
        clients (dict): Dictionary tracking client sockets and associated rooms.
        authenticated_clients (dict): Dictionary of authenticated clients and their usernames.

    Returns:
        None: Sends the game end status to both players and viewers, updates the room state.
    """
    board_status = (
        "GAMEEND:"
        + rooms[roomname].get_matrix_in_string()
        + ":2:"
    )
    for user in authenticated_clients.values():
        if is_same_socket(
            get_key_by_value(authenticated_clients,user),
            rooms[roomname].get_next_turn_player()
        ):
            winner = user
            board_status = board_status + winner
    sender_socket.sendall(board_status.encode('utf-8'))
    another_player = rooms[roomname].get_another_player(sender_socket)
    another_player.sendall(board_status.encode('utf-8'))
    rooms[roomname].send_to_all_viewers(board_status)

    new_clients = {
        k: v
        for k, v in clients.items()
        if (
            not is_same_socket(k, sender_socket))
            and not is_same_socket(
                k,
                rooms[roomname].get_another_player(sender_socket)
            )
    }
    new_clients[sender_socket] = None
    new_clients[rooms[roomname].get_another_player(sender_socket)] = None
    clients.clear()
    clients.update(new_clients)

    my_dict = {k: v for k, v in rooms.items() if k != roomname}
    rooms.clear()
    rooms.update(my_dict)


def place(splited_message, sender_socket, roomname, rooms, clients, authenticated_clients):
    """
    Handles placing a move in the game and updates the game board for all players and viewers.

    Args:
        splited_message (list): A list containing the move details (row, column).
        sender_socket (socket): The client's socket for sending responses.
        roomname (str): The name of the room where the game is being played.
        rooms (dict): The current in-memory dictionary of rooms and their states.
        clients (dict): A dictionary of connected clients.
        authenticated_clients (dict): A dictionary of authenticated users and their sockets.

    Returns:
        None: Sends the updated board or game status to both players and all viewers.
    """
    row = int(splited_message[2])
    column = int(splited_message[1])
    rooms[roomname] = rooms[roomname].update_matrix(row,column)
    if not rooms[roomname].get_has_end():
        board_status = (
            "BOARDSTATUS:"
            + rooms[roomname].get_matrix_in_string()
        )
    else:
        status_code = rooms[roomname].get_status_code()
        board_status = (
            "GAMEEND:"
            + rooms[roomname].get_matrix_in_string()
            + ":"
            + status_code
        )
        if status_code == "0":
            for user in authenticated_clients.values():
                if is_same_socket(
                    get_key_by_value(authenticated_clients,user)
                    , rooms[roomname].get_next_turn_player()
                ):
                    winner = user
            board_status = board_status + ":" + winner

    sender_socket.sendall(board_status.encode('utf-8'))
    another_player = rooms[roomname].get_another_player(sender_socket)
    another_player.sendall(board_status.encode('utf-8'))
    rooms[roomname].send_to_all_viewers(board_status)

    if rooms[roomname].get_has_end():
        new_clients = {
            k: v
            for k, v in clients.items()
            if (
                not is_same_socket(k, sender_socket))
                and not is_same_socket(
                    k,
                    rooms[roomname].get_another_player(sender_socket)
            )
        }
        new_clients[sender_socket] = None
        new_clients[
            rooms[roomname].get_another_player(sender_socket)
        ] = None
        clients.clear()
        clients.update(new_clients)

        my_dict = {k: v for k, v in rooms.items() if k != roomname}
        rooms.clear()
        rooms.update(my_dict)

def join_room(splited_message, sender_socket, rooms, clients, authenticated_clients):
    """
    Allows a client to join a game room either as a player or a viewer.

    Args:
        splited_message (list): A list containing room name and the role (PLAYER/VIEWER).
        sender_socket (socket): The client's socket for sending responses.
        rooms (dict): The current in-memory dictionary of rooms and their states.
        clients (dict): A dictionary of connected clients.
        authenticated_clients (dict): A dictionary of authenticated users and their sockets.

    Returns:
        None: Sends appropriate room join status and updates the room and client information.
    """
    if (
        len(splited_message) != 2
        or (
            splited_message[1] != 'VIEWER'
            and splited_message[1] != "PLAYER"
        )
    ):
        sender_socket.sendall("JOIN:ACKSTATUS:3".encode('utf-8'))
    else:
        room_name = splited_message[0]
        user_type = splited_message[1]

        if room_name in rooms:
            message_from_room = rooms.get(room_name).join(user_type)
            rooms[room_name] = rooms.get(room_name).update(sender_socket, user_type)
            sender_socket.sendall(message_from_room.encode('utf-8'))
            if (
                message_from_room == "JOIN:ACKSTATUS:0"
                and user_type == "PLAYER"
                and not rooms.get(room_name).able_to_add_player()
            ):
                another_player = rooms.get(room_name).get_another_player(sender_socket)
                for user in authenticated_clients.values():
                    if is_same_socket(
                        get_key_by_value(authenticated_clients,user),
                        another_player
                    ):
                        player_1 = user
                    elif is_same_socket(
                        get_key_by_value(authenticated_clients,user),
                        sender_socket
                    ):
                        player_2 = user
                begin_message = "BEGIN:" + player_1 + ":" + player_2
                another_player.sendall(begin_message.encode('utf-8'))
                sender_socket.sendall(begin_message.encode('utf-8'))
                rooms.get(room_name).send_to_all_viewers("INPROGRESS:" + player_1 + ":" + player_2)
                new_clients = {
                    k: v
                    for k, v in clients.items()
                    if not is_same_socket(k, sender_socket)
                }
                new_clients[sender_socket] = room_name
                clients.clear()
                clients.update(new_clients)
            elif (
                message_from_room == "JOIN:ACKSTATUS:0"
                and user_type == "VIEWER"
                and not rooms.get(room_name).able_to_add_player()
            ):
                current_player = rooms.get(room_name).get_current_player()
                next_player = rooms.get(room_name).get_next_turn_player()
                for user in authenticated_clients.values():
                    if is_same_socket(
                        get_key_by_value(authenticated_clients,user),
                        current_player
                    ):
                        player_1 = user
                    elif is_same_socket(
                        get_key_by_value(authenticated_clients,user),
                        next_player
                    ):
                        player_2 = user
                view_begin_message = "INPROGRESS:" + player_1 + ":" + player_2
                sender_socket.sendall(view_begin_message.encode('utf-8'))

        else:
            sender_socket.sendall("JOIN:ACKSTATUS:1".encode('utf-8'))

def create_room(splited_message, sender_socket, rooms, clients):
    """
    Handles creating a new game room.

    Args:
        splited_message (list): A list containing the desired room name.
        sender_socket (socket): The client's socket for sending responses.
        rooms (dict): The current in-memory dictionary of rooms and their states.
        clients (dict): A dictionary of connected clients.

    Returns:
        None: Sends appropriate room creation status and updates room and client lists.
    """
    if len(splited_message) != 1:
        sender_socket.sendall("CREATE:ACKSTATUS:4".encode('utf-8'))
    else:
        new_room_name = splited_message[0]
        if check_legal_room_name(new_room_name):
            if new_room_name in rooms:
                sender_socket.sendall("CREATE:ACKSTATUS:2".encode('utf-8'))
            elif len(rooms) == 256:
                sender_socket.sendall("CREATE:ACKSTATUS:3".encode('utf-8'))
            else:
                sender_socket.sendall("CREATE:ACKSTATUS:0".encode('utf-8'))
                new_room = Room(sender_socket)
                rooms[new_room_name] = new_room
                new_clients = {
                    k: v
                    for k, v in clients.items()
                    if not is_same_socket(k, sender_socket)
                }
                new_clients[sender_socket] = new_room_name
                clients.clear()
                clients.update(new_clients)
        else:
            sender_socket.sendall("CREATE:ACKSTATUS:1".encode('utf-8'))

def check_legal_room_name(room_name):
    """
    Validates the provided room name against the allowed pattern.

    Args:
        room_name (str): The name of the room to be validated.

    Returns:
        bool: True if the room name is valid, False otherwise.
    """
    pattern = r'^[a-zA-Z0-9 _-]{1,20}$'
    if re.match(pattern, room_name):
        return True
    return False

def room_list(splited_message, sender_socket, rooms):
    """
    Sends the list of available rooms to the client based on their type (PLAYER/VIEWER).

    Args:
        splited_message (list): A list containing the client type (PLAYER/VIEWER).
        sender_socket (socket): The client's socket for sending responses.
        rooms (dict): The current in-memory dictionary of rooms and their states.

    Returns:
        None: Sends the list of valid rooms to the requesting client.
    """
    if (
        len(splited_message) != 1
        or (
            splited_message[0] != 'PLAYER'
            and splited_message[0] != 'VIEWER'
        )
    ):
        sender_socket.sendall("ROOMLIST:ACKSTATUS:1".encode('utf-8'))
    else:
        client_type = splited_message[0]
        rooms_name_list = []
        if client_type == "VIEWER":
            rooms_name_list = rooms.keys()
        elif client_type == "PLAYER":
            for room_a in rooms.keys():
                if rooms.get(room_a).able_to_add_player():
                    rooms_name_list.append(room_a)
        roomlist  = ','.join(rooms_name_list)
        reply = "ROOMLIST:ACKSTATUS:0:" + roomlist
        sender_socket.sendall(reply.encode('utf-8'))

def login(splited_message, sender_socket, authenticated_clients, users):
    """
    Handles user authentication by verifying username and password.

    Args:
        splited_message (list): A list containing the username and password.
        sender_socket (socket): The client's socket for sending responses.
        authenticated_clients (dict): A dictionary of authenticated users and their sockets.
        users (dict): A dictionary of users with their hashed passwords.

    Returns:
        None: Sends appropriate login status and updates authenticated clients.
    """
    if (
        len(splited_message) != 2
        or splited_message[0] == ''
        or splited_message[1] == ''
    ):
        sender_socket.sendall("LOGIN:ACKSTATUS:3".encode('utf-8'))
    else:
        username = splited_message[0]
        password = splited_message[1]
        if username in users:
            user_input_password = password.encode('utf-8')
            if bcrypt.checkpw(user_input_password, users.get(username)):
                username_logined = False
                for used_username in authenticated_clients.values():
                    if username == used_username:
                        username_logined = True
                        break
                if username_logined:
                    #when you try to login in as  a used  username
                    sender_socket.sendall("LOGIN:ACKSTATUS:4".encode('utf-8'))
                elif check_authorizations(sender_socket,authenticated_clients):
                    #when you have already logined in
                    sender_socket.sendall("LOGIN:ACKSTATUS:5".encode('utf-8'))
                else:
                    sender_socket.sendall("LOGIN:ACKSTATUS:0".encode('utf-8'))
                    authenticated_clients[sender_socket] = username
            else:
                sender_socket.sendall("LOGIN:ACKSTATUS:2".encode('utf-8'))
        else:
            sender_socket.sendall("LOGIN:ACKSTATUS:1".encode('utf-8'))

def check_authorizations(sender_socket,authenticated_clients):
    """
    Checks if a given client is already authenticated.

    Args:
        sender_socket (socket): The client's socket.
        authenticated_clients (dict): A dictionary of authenticated users and their sockets.

    Returns:
        bool: True if the client is authenticated, False otherwise.
    """
    for old_socket in authenticated_clients.keys():
        if  is_same_socket(old_socket,sender_socket):
            return True
    return False


def register(splited_message, sender_socket, users, user_database_path):
    """
    Handles user registration by validating input and updating the user database.

    Args:
        splited_message (list): A list containing the username and password sent by the client.
        sender_socket (socket): The client's socket for sending responses.
        users (dict): The current in-memory dictionary of users with hashed passwords.
        user_database_path (str): The file path to the user database in JSON format.

    Returns:
        None: Sends appropriate response to the client based on registration status.
    """
    if (len(splited_message) != 2) or (splited_message[0] == '' or splited_message[1] == ''):
        sender_socket.sendall("REGISTER:ACKSTATUS:2".encode('utf-8'))
    else:
        username = splited_message[0]
        password = splited_message[1]
        if username in users:
            sender_socket.sendall("REGISTER:ACKSTATUS:1".encode('utf-8'))
        else:
            users[username]=hash_password(password)
            expanded_database_path = os.path.expanduser(user_database_path)
            users_data = []
            with open(expanded_database_path, 'r', encoding='utf-8') as db_file:
                try:
                    users_data = json.load(db_file)
                except json.JSONDecodeError:
                    sys.exit(1)
            db_file.close()

            users_data.append({
                "username": username,
                "password": hash_password(password).decode('utf-8')
            })

            with open(expanded_database_path, 'w', encoding='utf-8') as db_file:
                json.dump(users_data, db_file, indent=4)
            db_file.close()

            sender_socket.sendall("REGISTER:ACKSTATUS:0".encode('utf-8'))

def get_key_by_value(d, value):
    """
    Retrieves the key associated with a given value in a dictionary.

    This function is useful when dealing with socket objects, where the file 
    descriptor (fd) may change during the program's execution. Since directly 
    use keys(socket objects) in the dictionary may fail due to these changes, 
    this function allows finding the key(socket) based on the value.

    Args:
        d (dict): The dictionary to search.
        value: The value to find the corresponding key for.

    Returns:
        The key associated with the given value, or None if not found.
    """
    for k, v in d.items():
        if v == value:
            return k
    return None

def hash_password(user_input):
    """
    Hashes the given user password using bcrypt with a randomly generated salt.

    Args:
        user_input (str): The plain text password to be hashed.

    Returns:
        bytes: The hashed password, including the salt.
    """
    password =  user_input.encode('utf-8')
    salt =  bcrypt.gensalt()
    hashed_password  = bcrypt.hashpw(password, salt)

    return hashed_password

def is_same_socket(socket1, socket2):
    """
    Checks if two sockets are the same by comparing their local and remote addresses.

    This comparison is done using the local (getsockname) and remote (getpeername) addresses
    of the sockets because the file descriptors (fd) of sockets may sometimes change, making
    direct comparison unreliable.

    Args:
        socket1: The first socket to compare.
        socket2: The second socket to compare.

    Returns:
        bool: True if both sockets have the same local and remote addresses, False otherwise.
    """
    return (
        socket1.getsockname() == socket2.getsockname() and
        socket1.getpeername() == socket2.getpeername()
    )

def read_user_database(database_path):
    """
    Reads the user database from the specified JSON file.

    Args:
        database_path (str): Path to the user database file.

    Returns:
        list: A list of user records.

    """
    expanded_database_path = os.path.expanduser(database_path)

    if not os.path.exists(expanded_database_path):
        print(f"Error: {expanded_database_path} doesn't exist.", file=sys.stderr)
        sys.exit(0)

    try:
        with open(expanded_database_path, 'r', encoding='utf-8') as db_file:
            users_from_file = json.load(db_file)
    except json.JSONDecodeError:
        print(f"Error: {expanded_database_path} is not in a valid JSON format.", file=sys.stderr)
        sys.exit(1)
    db_file.close()

    if not isinstance(users_from_file, list):
        print(f"Error: {expanded_database_path} is not a JSON array.", file=sys.stderr)
        sys.exit(0)

    for user in users_from_file:
        if (
            not isinstance(user, dict)
            or 'username' not in user
            or 'password' not in user
            or len(user) > 2
        ):
            print(
                f"Error: {expanded_database_path} contains invalid user record formats.",
                file=sys.stderr
            )
            sys.exit(0)


    return users_from_file

if __name__ == "__main__":
    main(sys.argv[1:])
