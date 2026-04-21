import socket
import threading
import time

from game import GameManager
from protocol import parse_http_path, http_response, format_board_state, format_message


HOST = "0.0.0.0"
PORT = 8090

manager = GameManager()


def auto_unlock(game, category, player_name, seconds=5):
    time.sleep(seconds)
    ok, _ = game.unlock_category(category, player_name)
    if ok:
        game.broadcast(format_message("INFO", f"{category} desbloqueada automáticamente"))
        game.broadcast(format_board_state(game.board_state()))


def game_timer(game):
    while True:
        time.sleep(1)

        if game.is_finished():
            game.broadcast(format_message("END", "La partida ha terminado"))
            game.broadcast(format_board_state(game.board_state()))
            break


def handle_http(client_socket, request_text):
    parsed = parse_http_path(request_text)

    if parsed is None:
        client_socket.sendall(http_response(400, {"error": "Petición inválida"}))
        client_socket.close()
        return

    method, path = parsed

    if method != "GET":
        client_socket.sendall(http_response(400, {"error": "Solo se permite GET"}))
        client_socket.close()
        return

    if path == "/stop/new":
        game_id, _ = manager.create_game()
        client_socket.sendall(http_response(200, {
            "message": "Partida creada",
            "game_id": game_id
        }))
        client_socket.close()
        return

    if path.startswith("/stop/"):
        game_id = path.split("/stop/")[-1]
        game = manager.get_game(game_id)

        if game is None:
            client_socket.sendall(http_response(404, {"error": "Partida no encontrada"}))
        else:
            client_socket.sendall(http_response(200, {
                "message": "Partida encontrada",
                "game_id": game_id
            }))
        client_socket.close()
        return

    client_socket.sendall(http_response(404, {"error": "Ruta no encontrada"}))
    client_socket.close()


def recv_line(sock):
    data = b""
    while True:
        chunk = sock.recv(1)
        if not chunk:
            return None
        if chunk == b"\n":
            break
        data += chunk
    return data.decode().strip()


def handle_game_connection(client_socket):
    client_socket.sendall(b"GAME_ID:\n")
    game_id = recv_line(client_socket)

    client_socket.sendall(b"PLAYER_NAME:\n")
    player_name = recv_line(client_socket)

    game = manager.get_game(game_id)
    if game is None:
        client_socket.sendall((format_message("ERROR", "Partida no existe") + "\n").encode())
        client_socket.close()
        return

    game.add_player(player_name, client_socket)
    game.broadcast(format_message("INFO", f"{player_name} se ha unido a la partida {game_id}"))
    game.broadcast(format_board_state(game.board_state()))

    try:
        while True:
            raw = recv_line(client_socket)
            if raw is None:
                break

            if raw == "GO!":
                ok, result = game.start_game()
                if ok:
                    game.broadcast(format_message("START", f"Partida iniciada con letra {result}"))
                    game.broadcast(format_board_state(game.board_state()))

                    timer_thread = threading.Thread(target=game_timer, args=(game,), daemon=True)
                    timer_thread.start()
                else:
                    client_socket.sendall((format_message("ERROR", result) + "\n").encode())

            elif raw == "BOARD":
                client_socket.sendall((format_board_state(game.board_state()) + "\n").encode())

            elif raw.startswith("LOCK:"):
                _, category = raw.split(":", 1)
                ok, msg = game.lock_category(category, player_name)

                if ok:
                    game.broadcast(format_message("INFO", f"{player_name} ha bloqueado {category}"))
                    game.broadcast(format_board_state(game.board_state()))

                    unlock_thread = threading.Thread(
                        target=auto_unlock,
                        args=(game, category, player_name, 5),
                        daemon=True
                    )
                    unlock_thread.start()
                else:
                    client_socket.sendall((format_message("ERROR", msg) + "\n").encode())

            elif raw.startswith("UNLOCK:"):
                _, category = raw.split(":", 1)
                ok, msg = game.unlock_category(category, player_name)

                if ok:
                    game.broadcast(format_message("INFO", f"{player_name} ha desbloqueado {category}"))
                    game.broadcast(format_board_state(game.board_state()))
                else:
                    client_socket.sendall((format_message("ERROR", msg) + "\n").encode())

            elif raw.startswith("WRITE:"):
                parts = raw.split(":", 2)
                if len(parts) != 3:
                    client_socket.sendall((format_message("ERROR", "Formato inválido") + "\n").encode())
                    continue

                _, category, word = parts
                ok, msg = game.write_category(category, word, player_name)

                if ok:
                    game.broadcast(format_message("INFO", f"{player_name} ha escrito {word} en {category}"))
                    game.broadcast(format_board_state(game.board_state()))

                    if game.is_finished():
                        game.broadcast(format_message("END", "La partida ha terminado"))
                        game.broadcast(format_board_state(game.board_state()))
                        break
                else:
                    client_socket.sendall((format_message("ERROR", msg) + "\n").encode())

            elif raw == "EXIT":
                break

            else:
                client_socket.sendall((format_message("ERROR", "Comando desconocido") + "\n").encode())

    finally:
        game.remove_player(player_name)
        game.broadcast(format_message("INFO", f"{player_name} ha salido"))
        client_socket.close()


def handle_client(client_socket, address):
    try:
        first_data = client_socket.recv(4096)
        if not first_data:
            client_socket.close()
            return

        text = first_data.decode(errors="ignore")

        if text.startswith("GET "):
            handle_http(client_socket, text)
            return

        buffer = text
        if buffer:
            def fake_recv_line(initial_text):
                lines = initial_text.split("\n", 1)
                line = lines[0].strip()
                rest = lines[1] if len(lines) > 1 else ""
                return line, rest

            # Reinyectar la conexión de juego desde cero es más limpio.
            # Así evitamos inconsistencias por haber consumido ya datos.
            client_socket.close()
            return

    except Exception as e:
        print(f"Error con {address}: {e}")
        try:
            client_socket.close()
        except:
            pass


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()

    print(f"Servidor escuchando en {HOST}:{PORT}")

    while True:
        client_socket, address = server.accept()

        # Distinguir HTTP de juego con una conexión separada es más robusto,
        # así que este puerto se deja para HTTP.
        thread = threading.Thread(target=handle_http_entry, args=(client_socket, address), daemon=True)
        thread.start()


def handle_http_entry(client_socket, address):
    try:
        data = client_socket.recv(4096)
        if not data:
            client_socket.close()
            return

        text = data.decode(errors="ignore")
        handle_http(client_socket, text)
    except Exception as e:
        print(f"Error HTTP con {address}: {e}")
        try:
            client_socket.close()
        except:
            pass


def start_game_server():
    host = HOST
    port = 8091

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen()

    print(f"Servidor de juego escuchando en {host}:{port}")

    while True:
        client_socket, address = server.accept()
        thread = threading.Thread(target=handle_game_connection, args=(client_socket,), daemon=True)
        thread.start()


if __name__ == "__main__":
    t1 = threading.Thread(target=start_server, daemon=True)
    t2 = threading.Thread(target=start_game_server, daemon=True)

    t1.start()
    t2.start()

    t1.join()
    t2.join()
