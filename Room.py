"""
This module provides the Room class for managing game rooms.
"""

class Room:
    """
    A class to represent a game room.

    Attributes:
    ----------
    players : list
        A list of sockets for players in the room.
    viewers : list
        A list of sockets for viewers in the room.
    max_players : int
        The maximum number of players allowed in the room.
    matrix : list
        A 3x3 matrix representing the game board.
    current_player : socket
        The socket of the current player.
    has_end : bool
        A boolean indicating whether the game has ended.
    status_code : str
        A string representing the current game status(will send to players and viewers if someone won).
    has_began : bool
        A boolean indicating whether the game has started.
    """

    def __init__(self, sender_socket):
        """
        Initializes the Room class with the first player.

        Parameters:
        ----------
        sender_socket : socket
            The socket of the player initiating the room.
        """
        self.players = []
        self.players.append(sender_socket)
        self.viewers = []
        self.max_players = 2
        self.matrix = [[0 for _ in range(3)] for _ in range(3)]
        self.current_player = self.players[0]
        self.has_end = False
        self.status_code = "3"
        self.has_began = False

    def join(self, mode):
        """
        Check if the room is able to add PLAYER or VIEWER and return message

        Parameters:
        ----------
        mode : str
            The role of the participant, either 'PLAYER' or 'VIEWER'.

        Returns:
        -------
        str
            Returns a status code for joining the room.
        """
        if mode == "PLAYER":
            if len(self.players) < self.max_players:
                self.has_began = True
                return "JOIN:ACKSTATUS:0"
            return "JOIN:ACKSTATUS:2"
        return "JOIN:ACKSTATUS:0"

    def get_status_code(self):
        """
        Gets the current game status code. (normal wining, draw, forfeit)

        Returns:
        -------
        str
            The current game status code.
        """
        return  self.status_code

    def get_has_began(self):
        """
        Checks if the game has started.

        Returns:
        -------
        bool
            True if the game has started, False otherwise.
        """
        return self.has_began

    def get_has_end(self):
        """
        Checks if the game has ended.

        Returns:
        -------
        bool
            True if the game has ended, False otherwise.
        """
        return self.has_end

    def check_end_status(self):
        """
        Checks if the game has reached an end state by checking the matrix for win conditions.
        """
        if self.check_rows() or self.check_columns() or self.check_diagonals():
            self.status_code = "0"
            self.has_end = True
            return

        if self.is_board_full():
            # If the board is full and no winner, it's a draw
            self.status_code = "1"
            self.has_end = True

    def check_rows(self):
        """
        Checks if there is a winner in any row.

        Returns:
        -------
        bool: True if there is a winner, False otherwise.
        """
        for row in self.matrix:
            if row[0] == row[1] == row[2] and row[0] != 0:
                return True
        return False

    def check_columns(self):
        """
        Checks if there is a winner in any column.

        Returns:
        -------
        bool: True if there is a winner, False otherwise.
        """
        for col in range(3):
            if self.matrix[0][col] == self.matrix[1][col] == self.matrix[2][col] and self.matrix[0][col] != 0:
                return True
        return False

    def check_diagonals(self):
        """
        Checks if there is a winner in any diagonal.

        Returns:
        -------
        bool: True if there is a winner, False otherwise.
        """
        # Check top-left to bottom-right diagonal
        if self.matrix[0][0] == self.matrix[1][1] == self.matrix[2][2] and self.matrix[0][0] != 0:
            return True
        # Check top-right to bottom-left diagonal
        if self.matrix[0][2] == self.matrix[1][1] == self.matrix[2][0] and self.matrix[0][2] != 0:
            return True
        return False

    def is_board_full(self):
        """
        Checks if the board is full.

        Returns:
        -------
        bool: True if the board is full, False otherwise.
        """
        return all(0 not in row for row in self.matrix)

    def get_matrix_in_string(self):
        """
        Converts the matrix to a string representation.

        Returns:
        -------
        str
            The matrix in string format.
        """
        return ''.join(str(num) for row in self.matrix for num in row)

    def get_current_player(self):
        """
        Gets the current player(the one who has the turn to place).

        Returns:
        -------
        socket
            The socket of the current player.
        """
        if self.current_player  == self.players[0]:
            return self.players[0]
        return self.players[1]

    def get_next_turn_player(self):
        """
        Gets the next player who will take a turn.

        Returns:
        -------
        socket
            The socket of the next player.
        """
        if self.current_player  == self.players[0]:
            return self.players[1]
        return self.players[0]

    def send_to_all_viewers(self, message):
        """
        Sends a message to all viewers.

        Parameters:
        ----------
        message : str
            The message to send to the viewers.
        """
        for viewer in self.viewers:
            viewer.sendall(message.encode('utf-8'))

    def update_matrix(self,row,column):
        """
        Updates the game matrix with the current player's move.

        Parameters:
        ----------
        row : int
            The row index of the move.
        column : int
            The column index of the move.
        """
        if self.current_player == self.players[0]:
            self.matrix[row][column] = 1
            self.current_player = self.players[1]
        else:
            self.matrix[row][column] = 2
            self.current_player = self.players[0]
        self.check_end_status()
        return self

    def update(self, sender_socket, mode):
        """
        Adds a player or viewer to the game.

        Parameters:
        ----------
        sender_socket : socket
            The socket of the player or viewer.
        mode : str
            The mode, either 'PLAYER' or 'VIEWER'.
        """
        if mode == "PLAYER":
            if len(self.players) < self.max_players:
                self.players.append(sender_socket)
                self.has_began = True
        elif mode == "VIEWER":
            self.viewers.append(sender_socket)
        return self

    def get_another_player(self,sender_socket):
        """
        Gets the player other than the sender.

        Parameters:
        ----------
        sender_socket : socket
            The socket of the sender.

        Returns:
        -------
        socket
            The socket of the other player.
        """
        i = 0
        while i<2:
            if is_same_socket(self.players[i], sender_socket):
                break
            i += 1
        if i == 0:
            return self.players[1]
        return self.players[0]

    def able_to_add_player(self):
        """
        Checks if another player can be added to the room.

        Returns:
        -------
        bool
            True if a player can be added, False otherwise.
        """
        return len(self.players) < self.max_players

    def in_room_as_a_player(self,sender_socket):
        """
        Checks if the sender is in the room as a player.

        Parameters:
        ----------
        sender_socket : socket
            The socket of the sender.

        Returns:
        -------
        bool
            True if the sender is a player, False otherwise.
        """
        return any(is_same_socket(player_socket, sender_socket) for player_socket in self.players)

def is_same_socket(socket1, socket2):
    """
    Checks if two sockets are the same.

    Parameters:
    ----------
    socket1 : socket
        The first socket.
    socket2 : socket
        The second socket.

    Returns:
    -------
    bool
        True if the two sockets are the same, False otherwise.
    """
    return (
        socket1.getsockname() == socket2.getsockname() and
        socket1.getpeername() == socket2.getpeername()
    )
