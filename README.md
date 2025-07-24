# Tic-Tac-Toe Multiplayer Server (Python)

A solo project (Sept – Oct 2024) that delivers a real-time, networked Tic-Tac-Toe experience.  
It includes:

* **Python server** – manages user accounts, game rooms, and live gameplay with viewers.  
* **CLI client** – lets players (or spectators) connect, chat with the server, and play.  
* **Reusable game engine** – pure-Python logic for classic 3 × 3 Tic-Tac-Toe.

---

## Key Features
| Area | Highlights |
|------|------------|
| **Accounts** | Register & log in (bcrypt-hashed passwords stored in a JSON database). |
| **Rooms** | Create or join up to 256 named rooms. Each room supports 2 players + unlimited viewers. |
| **Gameplay** | Real-time board updates, turn tracking, win/draw/forfeit detection, and automatic clean-up when a player disconnects. |
| **Persistence** | Small JSON config file drives server settings; user DB survives restarts. |
| **Scalability** | Uses Python `multiprocessing` so each client connection is handled in its own process. |
| **Modularity** | Core game logic lives in `game.py`; socket protocol & room state live in `server.py` / `Room.py`. |

---

## Project Structure
```
.
├── game.py          # Stand-alone Tic-Tac-Toe logic (create board, check wins, etc.)
├── tictactoe.py     # Quick local demo using game.py
├── server.py        # Entry point for the multiplayer server
├── client.py        # Command-line client
├── Room.py          # Room class (board state + player/viewer management)
├── sample_config.json
└── users.json       # (generated) bcrypt-hashed credentials
```

---

## Getting Started

### 1. Clone & install
```bash
git clone https://github.com/your-handle/tictactoe-server.git
cd tictactoe-server
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install bcrypt
```

### 2. Create a server config
```jsonc
// sample_config.json
{
  "port": 5050,
  "userDatabase": "users.json"
}
```

### 3. Launch the server
```bash
python server.py sample_config.json
```
> The server prints **“Server is listening on port 5050…”** when ready.

### 4. Run the client
```bash
# Syntax: python client.py <server address> <port>
python client.py 127.0.0.1 5050
```

---

## Client Commands (cheat‑sheet)

| Command   | Arguments (prompted) | Purpose          |
|-----------|----------------------|------------------|
| `LOGIN`   | username, password   | Authenticate     |
| `REGISTER`| username, password   | Create an account|
| `ROOMLIST`| Player \| Viewer    | List rooms       |
| `CREATE`  | room‑name            | New room (P1)    |
| `JOIN`    | room‑name, role      | Enter a room     |
| `PLACE`   | column, row (0‑2)    | Make a move      |
| `FORFEIT` | –                    | Concede          |
| `QUIT`    | –                    | Disconnect       |

---

## Protocol Overview

Messages are plain UTF‑8 strings in the form  
`<TYPE>:<payload1>:<payload2>...`

Examples:

* `LOGIN:alice:secretpass`  
* `CREATE:room42`  
* Server reply `BEGIN:alice:bob` starts the match and names the two players.

See `client.py` and `server.py` for the full state machine.

---

## Testing Locally

1. Start the server in one terminal.  
2. Open **two** extra terminals and run the client in each.  
3. Register accounts, create a room from the first client, join from the second, and start placing moves.

---

## Security Notes
* Passwords use **bcrypt**; salts are random – rainbow‑table safe.  
* Sockets are unencrypted for simplicity. Wrap the connection in TLS (e.g., stunnel or Python `ssl`) if used across networks.

---

## Future Work / Ideas
* WebSocket front‑end for browser play.  
* Dockerfile & CI workflow.  
* AI opponent for single‑player practice.  
* HTTP REST admin endpoint for live room monitoring.

---

## License
MIT – do anything, but give credit.

---

### Author

**Yunfei Bai* – Advanced Computing student @ The University of Sydney  
*Solo development, Sept – Oct 2024*
