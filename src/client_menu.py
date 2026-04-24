import socket
import threading
import json
from urllib.request import urlopen
from urllib.error import URLError, HTTPError


HTTP_PORT = 8090
GAME_PORT = 8091
DEFAULT_HOST = "127.0.0.1"

CATEGORIES = [
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


class ClientState:
    def __init__(self):
        self.game_id = None
        self.player_name = None
        self.board_data = None
        self.running = True


state = ClientState()


def print_separator():
    print("\n" + "=" * 60)


def pretty_category_name(category):
    return category


def print_board(board_data):
    print_separator()
    print(f"Partida: {board_data['game_id']}")
    print(f"Ronda: {board_data.get('current_round', 1)}/{board_data.get('total_rounds', 1)}")
    print(f"Iniciada: {'Sí' if board_data['started'] else 'No'}")
    print(f"Terminada: {'Sí' if board_data.get('finished', False) else 'No'}")
    print(f"Letra: {board_data['letter'] if board_data['letter'] else '-'}")

    players = board_data.get("players", [])
    print(f"Jugadores: {', '.join(players) if players else '-'}")
    print("-" * 60)

    board = board_data["board"]
    locks = board_data["locks"]
    completed_by = board_data.get("completed_by", {})

    for category in board:
        value = board[category] if board[category] else "[vacío]"
        locked_by = locks.get(category)
        author = completed_by.get(category)

        extra = ""
        if locked_by is not None:
            extra += f"  🔒 bloqueado por {locked_by}"
        if author:
            extra += f"  ✅ completado por {author}"

        print(f"{pretty_category_name(category):<12}: {value}{extra}")

    print("-" * 60)
    print("Puntuaciones:")
    scores = board_data.get("scores", {})
    if scores:
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for i, (player, points) in enumerate(ranking, start=1):
            print(f"{i}. {player}: {points} puntos")
    else:
        print("Sin puntuaciones todavía")

    print("=" * 60 + "\n")


def handle_message(raw_message):
    raw_message = raw_message.strip()
    if not raw_message:
        return

    try:
        msg = json.loads(raw_message)
    except json.JSONDecodeError:
        print(raw_message)
        return

    msg_type = msg.get("type")
    data = msg.get("data")

    if msg_type == "INFO":
        print(f"\n[INFO] {data}")

    elif msg_type == "ERROR":
        print(f"\n[ERROR] {data}")

    elif msg_type == "ROUND_START":
        print(
            f"\n[RONDA] Empieza la ronda {data['round']}/{data['total_rounds']} con letra {data['letter']}"
        )

    elif msg_type == "ROUND_END":
        print(f"\n[RONDA] Ha terminado la ronda {data['round']}")
        print("Ranking provisional:")
        for i, (player, points) in enumerate(data["scores"], start=1):
            print(f"{i}. {player}: {points} puntos")

    elif msg_type == "END":
        print(f"\n[FIN] {data['message']}")
        print("Ranking final:")
        for i, (player, points) in enumerate(data["ranking"], start=1):
            print(f"{i}. {player}: {points} puntos")

    elif msg_type == "BOARD":
        state.board_data = data
        print_board(data)

    else:
        print(f"\n[DESCONOCIDO] {msg}")


def receive_messages(sock):
    buffer = ""

    while state.running:
        try:
            data = sock.recv(4096)
            if not data:
                print("\n[INFO] Conexión cerrada por el servidor.")
                state.running = False
                break

            buffer += data.decode()

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                handle_message(line)

        except Exception:
            if state.running:
                print("\n[ERROR] Error recibiendo mensajes del servidor.")
            state.running = False
            break


def http_get_json(host, path):
    url = f"http://{host}:{HTTP_PORT}{path}"
    with urlopen(url, timeout=5) as response:
        data = response.read().decode()
        return json.loads(data)


def create_game(host):
    try:
        print(f"\n[INFO] Intentando crear partida en http://{host}:{HTTP_PORT}/stop/new")
        data = http_get_json(host, "/stop/new")
        print(f"\n[OK] Partida creada con ID: {data['game_id']}")
        return data["game_id"]
    except HTTPError as e:
        print(f"\n[ERROR] HTTP {e.code}")
    except URLError as e:
        print(f"\n[ERROR] No se pudo contactar con el servidor HTTP: {e}")
    except Exception as e:
        print(f"\n[ERROR] {e}")
    return None


def check_game_exists(host, game_id):
    try:
        data = http_get_json(host, f"/stop/{game_id}")
        return data.get("game_id") == game_id
    except Exception:
        return False


def recv_line_blocking(sock):
    data = b""
    while True:
        chunk = sock.recv(1)
        if not chunk:
            break
        data += chunk
        if chunk == b"\n":
            break
    return data.decode()


def connect_game_socket(host, player_name, game_id):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((host, GAME_PORT))

    prompt1 = recv_line_blocking(client)
    print(prompt1, end="")
    client.sendall((game_id + "\n").encode())

    prompt2 = recv_line_blocking(client)
    print(prompt2, end="")
    client.sendall((player_name + "\n").encode())

    return client


def choose_category():
    print("\nElige categoría:")
    for i, cat in enumerate(CATEGORIES, start=1):
        print(f"{i}. {cat}")

    option = input("> ").strip()

    valid_options = {str(i) for i in range(1, len(CATEGORIES) + 1)}
    if option not in valid_options:
        print("[ERROR] Opción no válida.")
        return None

    return CATEGORIES[int(option) - 1]


def room_menu(sock):
    while state.running:
        print_separator()
        print("Acciones:")
        print("1. Ver tablero")
        print("2. Empezar partida")
        print("3. Bloquear categoría")
        print("4. Escribir palabra")
        print("5. Salir")
        option = input("> ").strip()

        if option == "1":
            sock.sendall(b"BOARD\n")

        elif option == "2":
            sock.sendall(b"GO!\n")

        elif option == "3":
            category = choose_category()
            if category:
                command = f"LOCK:{category}\n"
                sock.sendall(command.encode())

        elif option == "4":
            category = choose_category()
            if category:
                word = input("Escribe la palabra: ").strip()
                if not word:
                    print("[ERROR] No puedes enviar una palabra vacía.")
                    continue
                command = f"WRITE:{category}:{word}\n"
                sock.sendall(command.encode())

        elif option == "5":
            state.running = False
            try:
                sock.sendall(b"EXIT\n")
            except Exception:
                pass
            sock.close()
            print("\n[INFO] Has salido de la partida.")
            break

        else:
            print("[ERROR] Opción no válida.")


def main():
    print_separator()
    print("CLIENTE STOP")
    print_separator()

    host = input(f"IP del servidor [{DEFAULT_HOST}]: ").strip()
    if not host:
        host = DEFAULT_HOST

    player_name = input("Tu nombre de jugador: ").strip()
    if not player_name:
        print("[ERROR] El nombre no puede estar vacío.")
        return

    state.player_name = player_name

    while True:
        print_separator()
        print("Menú principal:")
        print("1. Crear partida")
        print("2. Unirse a partida")
        print("3. Salir")

        option = input("> ").strip()

        if option == "1":
            game_id = create_game(host)
            if not game_id:
                continue

            state.game_id = game_id
            break

        elif option == "2":
            game_id = input("Introduce el game_id: ").strip()
            if not game_id:
                print("[ERROR] Debes introducir un game_id.")
                continue

            exists = check_game_exists(host, game_id)
            if not exists:
                print("[ERROR] Esa partida no existe.")
                continue

            state.game_id = game_id
            break

        elif option == "3":
            print("Saliendo.")
            return

        else:
            print("[ERROR] Opción no válida.")

    try:
        sock = connect_game_socket(host, state.player_name, state.game_id)
    except Exception as e:
        print(f"\n[ERROR] No se pudo conectar al servidor de juego: {e}")
        return

    receiver = threading.Thread(target=receive_messages, args=(sock,), daemon=True)
    receiver.start()

    try:
        room_menu(sock)
    except KeyboardInterrupt:
        state.running = False
        try:
            sock.sendall(b"EXIT\n")
        except Exception:
            pass
        sock.close()
        print("\n[INFO] Cliente cerrado.")


if __name__ == "__main__":
    main()
