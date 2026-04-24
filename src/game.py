import threading
import random
import time

GAME_TIME = 300


class Game:
    def __init__(self, game_id):
        self.game_id = game_id
        self.players = {}   # player_name -> socket
        self.players_lock = threading.Lock()

        self.categories = [
            "animal",
            "lugar",
            "comida",
            "marca",
            "color",
            "famoso",
            "serie/peli",
            "objeto",
            "profesion",
            "deporte",
            "nombre"
        ]

        self.board = {cat: "" for cat in self.categories}
        self.locks = {cat: None for cat in self.categories}
        self.completed_by = {cat: None for cat in self.categories}

        self.started = False
        self.finished = False
        self.letter = None
        self.start_time = None
        self.max_time = GAME_TIME

        self.total_rounds = 3
        self.current_round = 1

        self.scores = {}   # player_name -> puntos

        self.state_lock = threading.Lock()

    def add_player(self, player_name, client_socket):
        with self.players_lock:
            if player_name in self.players:
                return False, "Nombre ya en uso"

            self.players[player_name] = client_socket

        with self.state_lock:
            if player_name not in self.scores:
                self.scores[player_name] = 0

        return True, "OK"

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

    def reset_round_board(self):
        self.board = {cat: "" for cat in self.categories}
        self.locks = {cat: None for cat in self.categories}
        self.completed_by = {cat: None for cat in self.categories}

    def start_game(self):
        with self.state_lock:
            if self.finished:
                return False, "La partida ya ha terminado"

            if self.started:
                return False, "La ronda ya ha comenzado"

            self.started = True
            self.letter = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            self.start_time = time.time()

            self.reset_round_board()

            return True, self.letter

    def start_next_round(self):
        with self.state_lock:
            if self.current_round >= self.total_rounds:
                self.finished = True
                return False, "No hay más rondas"

            self.current_round += 1
            self.started = True
            self.letter = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            self.start_time = time.time()

            self.reset_round_board()

            return True, self.letter

    def finish_game(self):
        with self.state_lock:
            self.finished = True
            self.started = False

    def finish_current_round(self):
        with self.state_lock:
            self.started = False
            for cat in self.categories:
                self.locks[cat] = None

    def lock_category(self, category, player_name):
        with self.state_lock:
            if self.finished:
                return False, "La partida ya ha terminado"

            if not self.started:
                return False, "La ronda no está en marcha"

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
            if self.finished:
                return False, "La partida ya ha terminado"

            if not self.started:
                return False, "La ronda no está en marcha"

            if category not in self.categories:
                return False, "Categoría no válida"

            if self.locks[category] != player_name:
                return False, "No tienes bloqueada esa categoría"

            if self.board[category] != "":
                return False, "Categoría ya completada"

            if not word:
                return False, "Palabra vacía"

            if self.letter is None:
                return False, "La ronda no ha comenzado"

            if word[0].upper() != self.letter:
                return False, f"La palabra debe empezar por {self.letter}"

            self.board[category] = word
            self.locks[category] = None
            self.completed_by[category] = player_name

            if player_name not in self.scores:
                self.scores[player_name] = 0

            self.scores[player_name] += 1

            return True, "OK"

    def is_round_complete(self):
        with self.state_lock:
            return all(self.board[cat] != "" for cat in self.categories)

    def is_round_time_over(self):
        with self.state_lock:
            if self.started and self.start_time is not None:
                return (time.time() - self.start_time) >= self.max_time
            return False

    def should_end_round(self):
        with self.state_lock:
            if not self.started:
                return False

            if all(self.board[cat] != "" for cat in self.categories):
                return True

            if self.start_time is not None and (time.time() - self.start_time) >= self.max_time:
                return True

            return False

    def get_ranking(self):
        with self.state_lock:
            ranking = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
            return ranking

    def board_state(self):
        with self.state_lock:
            return {
                "game_id": self.game_id,
                "started": self.started,
                "finished": self.finished,
                "current_round": self.current_round,
                "total_rounds": self.total_rounds,
                "letter": self.letter,
                "board": dict(self.board),
                "locks": dict(self.locks),
                "completed_by": dict(self.completed_by),
                "players": list(self.players.keys()),
                "scores": dict(self.scores)
            }


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
