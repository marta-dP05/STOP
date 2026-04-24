import threading
import random
import time


class Game:
    def __init__(self, game_id):
        self.game_id = game_id
        self.players = {}   # player_name -> socket
        self.players_lock = threading.Lock()

        self.categories = ["marca", "comida", "lugar", "animal"]
        self.board = {cat: "" for cat in self.categories}
        self.locks = {cat: None for cat in self.categories}   # cat -> player_name o None

        self.started = False
        self.finished = False
        self.letter = None
        self.start_time = None
        self.max_time = 300

        self.state_lock = threading.Lock()

    def add_player(self, player_name, client_socket):
        with self.players_lock:
            self.players[player_name] = client_socket

    def remove_player(self, player_name):
        with self.players_lock:
            if player_name in self.players:
                del self.players[player_name]

    def broadcast(self, message):
        dead = []
        with self.players_lock:
            for player_name, sock in self.players.items():
                try:
                    sock.sendall((message + "\n").encode())
                except:
                    dead.append(player_name)

            for player_name in dead:
                del self.players[player_name]

    def start_game(self):
        with self.state_lock:
            if self.started:
                return False, "La partida ya ha comenzado"

            self.started = True
            self.letter = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            self.start_time = time.time()

            self.board = {cat: "" for cat in self.categories}
            self.locks = {cat: None for cat in self.categories}

            return True, self.letter

    def lock_category(self, category, player_name):
        with self.state_lock:
            if category not in self.categories:
                return False, "Categoría no válida"

            if self.board[category] != "":
                return False, "Categoría ya completada"

            if self.locks[category] is not None and self.locks[category] != player_name:
                return False, f"Categoría bloqueada por {self.locks[category]}"

            self.locks[category] = player_name
            return True, "OK"

    def unlock_category(self, category, player_name):
        with self.state_lock:
            if category in self.categories and self.locks[category] == player_name:
                self.locks[category] = None
                return True, "OK"
            return False, "No puedes desbloquear esa categoría"

    def write_category(self, category, word, player_name):
        with self.state_lock:
            if category not in self.categories:
                return False, "Categoría no válida"

            if self.locks[category] != player_name:
                return False, "No tienes bloqueada esa categoría"

            if self.board[category] != "":
                return False, "Categoría ya completada"

            if not word:
                return False, "Palabra vacía"

            if self.letter is None:
                return False, "La partida no ha comenzado"

            if word[0].upper() != self.letter:
                return False, f"La palabra debe empezar por {self.letter}"

            self.board[category] = word
            self.locks[category] = None
            return True, "OK"

    def is_finished(self):
        with self.state_lock:
            if self.finished:
                return True

            if all(self.board[cat] != "" for cat in self.categories):
                self.finished = True
                return True

            if self.started and self.start_time is not None:
                if time.time() - self.start_time >= self.max_time:
                    self.finished = True
                    return True

            return False

    def board_state(self):
        with self.state_lock:
            return {
                "game_id": self.game_id,
                "started": self.started,
                "letter": self.letter,
                "board": dict(self.board),
                "locks": dict(self.locks),
                "players": list(self.players.keys())
            }

    def finish_game(self):
        with self.state_lock:
            self.finished = True


class GameManager:
    def __init__(self):
        self.games = {}
        self.lock = threading.Lock()

    def create_game(self):
        with self.lock:
            while True:
                game_id = str(random.randint(1000, 9999))
                if game_id not in self.games:
                    game = Game(game_id)
                    self.games[game_id] = game
                    return game_id, game

    def get_game(self, game_id):
        with self.lock:
            return self.games.get(game_id)

    def remove_game(self, game_id):
        with self.lock:
            if game_id in self.games:
                del self.games[game_id]
