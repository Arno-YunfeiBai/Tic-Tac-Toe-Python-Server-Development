import sys
import socket

def main(args: list[str]) -> None:
    # Begin here!
    if len(args) != 2:
        print("Error: Expecting 2 arguments: <server address> <port>", file=sys.stderr)
        sys.exit(0)

    server_address = args[0]
    try:
        port = int(args[1])
    except ValueError:
        print("Error: Port must be an integer.", file=sys.stderr)
        sys.exit(1)

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((server_address, port))
    except socket.error:
        print(f"Error: cannot connect to server at {server_address} and {port}.", file=sys.stderr)
        sys.exit(1)

    try:
        room_model = False
        waiting = False
        your_turn = False
        player = False
        user_type = None
        username = None
        room_name = None
        while True:
            if not room_model and not waiting:
                user_in_put = input()
                if user_in_put == "LOGIN":
                    username = input("Enter username:")
                    password = input("Enter password:")
                    message = "LOGIN:" + username + ":" + password
                elif user_in_put == "REGISTER":
                    username = input("Enter username:")
                    password = input("Enter password:")
                    message = "REGISTER:" + username + ":" + password
                elif user_in_put == "ROOMLIST":
                    user_type = input(
                        "Do you want to have a room list as player or viewer? (Player/Viewer)"
                    ).upper()
                    while user_type not in ("PLAYER", "VIEWER"):
                        print("Unknown input")
                        user_type = input(
                            "Do you want to have a room list as player or viewer? (Player/Viewer)"
                        ).upper()
                    message =  "ROOMLIST:" + user_type
                elif user_in_put == "CREATE":
                    room_name = input("Enter room name you want to create:")
                    message = "CREATE:" + room_name
                elif user_in_put == "JOIN":
                    room_name = input("Enter room name you want to join:")
                    user_type = input(
                        "You wish to join the room as: (Player/Viewer)"
                    ).upper()
                    while user_type not in ("PLAYER", "VIEWER"):
                        print("Unknown input")
                        user_type = input(
                            "You wish to join the room as: (Player/Viewer)"
                        ).upper()
                    message = "JOIN:" + room_name + ":" + user_type
                elif user_in_put.upper() == "QUIT":
                    message = "QUIT"
                else:
                    print(f"Unknown command: {user_in_put}")
                    continue

                if message == 'QUIT':
                    break

                client_socket.sendall(message.encode('utf-8'))

                data = client_socket.recv(8192)
                received_message = data.decode('utf-8').strip()

                waiting, your_turn, player = handle_outroom_message(
                    received_message,
                    username,
                    user_type,
                    room_name
                )

            elif waiting:
                data = client_socket.recv(8192)
                received_message = data.decode('utf-8').strip()

                splited_message = received_message.split(":")
                if splited_message[0] == "BEGIN": #player
                    board_status = "000000000"
                    print_board(board_status)
                    room_model = True
                    waiting = False
                    player = True
                    continue
                if splited_message[0] == "INPROGRESS": #viewers
                    board_status = "000000000"
                    print_board(board_status)
                    current_player = splited_message[1]
                    opposing_player = splited_message[2]
                    print(f"Match between {current_player} and {opposing_player} is currently in progress, it is {current_player}'s turn")
                    turn = current_player
                    room_model = True
                    waiting = False
            else:#in_room MODEL
                if your_turn and player:
                    print("It is the current player's turn")
                    user_in_put = input()

                    if user_in_put == "PLACE":
                        try:
                            column = int(input("Column: "))
                            row = int(input("Row: "))

                            # Check if the entered values are within the valid range
                            if (
                                column < 0
                                or column > 2
                                or row < 0
                                or row > 2
                            ):
                                print("Error: Column/Row values must be an integer between 0 and 2.")
                                continue
                        except ValueError:
                            print("Error: Column/Row values must be an integer between 0 and 2.")
                            continue

                        occupied, marker = is_position_occupied(board_status, column, row)
                        if occupied:
                            print(f"Position ({column}, {row}) is occupied by {marker}.")
                            continue
                        place_message = "PLACE:" + str(column) + ":" + str(row)
                        client_socket.sendall(place_message.encode('utf-8'))
                    elif user_in_put == "FORFEIT":
                        client_socket.sendall("FORFEIT".encode('utf-8'))
                    else:
                        print(f"Unknown command: {user_in_put}")
                        continue
                elif player and not your_turn:
                    print("It is the opposing player's turn")

                data = client_socket.recv(8192)
                received_message = data.decode('utf-8').strip()


                splited_message = received_message.split(":")

                if splited_message[0] == "BOARDSTATUS":
                    board_status = splited_message[1]
                    print_board(board_status)
                    if not player:
                        if turn == current_player:
                            print(f"it is {opposing_player}'s turn")
                            turn = opposing_player
                        elif turn == opposing_player:
                            print(f"it is {current_player}'s turn")
                            turn = current_player
                    if your_turn and player:
                        your_turn = False
                    elif (not your_turn) and player:
                        your_turn = True
                elif splited_message[0] == "GAMEEND":
                    board_status = splited_message[1]
                    print_board(board_status)
                    status = splited_message[2]
                    if status == "1":
                        print("Game ended in a draw")
                    elif status == "0":
                        winner = splited_message[3]
                        if player and your_turn:
                            print("Congratulations, you won!")
                        elif player and not your_turn:
                            print("Sorry you lost. Good luck next time.")
                        else:
                            print(f"{winner} has won this game")
                    elif status == "2":
                        winner = splited_message[3]
                        print(f"{winner} won due to the opposing player forfeiting")
                    room_model = False
                    waiting = False
                    your_turn = False
                    player = False

    except ConnectionResetError:
        print("Server has closed.")

    except ConnectionAbortedError:
        print("Server has closed.")

    except EOFError:
        print("EOF detected, closing connection.")

    finally:
        client_socket.close()

def print_board(board_status):

    board = [list(board_status[i:i+3]) for i in range(0, 9, 3)]
    symbols = {'0': ' ', '1': 'X', '2': 'O'}

    print("-" * 13)
    for i, row in enumerate(board):
        print("| " + " | ".join(symbols[cell] for cell in row) + " |")
        print("-" * 13)

def is_position_occupied(board_status, col, row):
    board = [list(board_status[i:i+3]) for i in range(0, 9, 3)]

    position_value = board[row][col]

    if position_value == '0':
        return False, None
    if position_value == '1':
        return True, 'X'
    if position_value == '2':
        return True, 'O'

def handle_outroom_message(received_message, username, user_type, room_name):
    waiting = False
    your_turn = False
    player = False
    splited_message = received_message.split(":")

    if received_message == "BADAUTH":
        print("Error: You must be logged in to perform this action", file=sys.stderr)
    elif  received_message == "NOROOM":
        print("No Room", file=sys.stderr)
    else:
        if received_message == "LOGIN:ACKSTATUS:0":
            print(f"Welcome {username}")
        elif received_message == "LOGIN:ACKSTATUS:1":
            print(f"Error: User {username} not found", file=sys.stderr)
        elif received_message == "LOGIN:ACKSTATUS:2":
            print(f"Error: Wrong password for user {username}", file=sys.stderr)
        elif received_message == "LOGIN:ACKSTATUS:3":
            print("Error: An invalid format message sent", file=sys.stderr)
        elif received_message == "LOGIN:ACKSTATUS:4":
            print(f"Error: User {username} is actively authenticated", file=sys.stderr)
        elif received_message == "LOGIN:ACKSTATUS:5":
            print("Error: You have already loginned", file=sys.stderr)
        elif received_message == "REGISTER:ACKSTATUS:0":
            print(f"Successfully created user account {username}")
        elif received_message == "REGISTER:ACKSTATUS:1":
            print(f"Error: User {username} already exists", file=sys.stderr)
        elif received_message == "REGISTER:ACKSTATUS:2":
            print("Error: An invalid format message sent", file=sys.stderr)
        elif splited_message[0] == "ROOMLIST":
            if splited_message[2] == "0":
                rooms = splited_message[-1]
                print(f"Room available to join as {user_type}: {rooms}")
            else:
                print("Error: Please input a valid mode.", file=sys.stderr)
        elif received_message == "CREATE:ACKSTATUS:0":
            print(f"Successfully created room {room_name}")
            print("Waiting for other player...")
            waiting = True
            your_turn = True
            player = True
        elif received_message == "CREATE:ACKSTATUS:1":
            print(f"Error: Room {room_name} is invalid", file=sys.stderr)
        elif received_message == "CREATE:ACKSTATUS:2":
            print(f"Error: Room {room_name} already exists", file=sys.stderr)
        elif received_message == "CREATE:ACKSTATUS:3":
            print("Error: Server already contains a maximum of 256 rooms", file=sys.stderr)
        elif received_message == "CREATE:ACKSTATUS:4":
            print("Error: An invalid format message sent", file=sys.stderr)
        elif received_message == "JOIN:ACKSTATUS:0":
            print(f"Successfully joined room {room_name} as a {user_type}")
            waiting = True
        elif received_message == "JOIN:ACKSTATUS:1":
            print(f"Error: No room named {room_name}", file=sys.stderr)
        elif received_message == "JOIN:ACKSTATUS:2":
            print(f"Error: The room {room_name} already has 2 players", file=sys.stderr)
        elif received_message == "JOIN:ACKSTATUS:3":
            print("Error: An invalid format message sent", file=sys.stderr)
        else:
            if received_message != "\n":
                print("Unknown message received from server. Exiting...", file=sys.stderr)
                sys.exit(0)

    return waiting, your_turn, player


if __name__ == "__main__":
    main(sys.argv[1:])
