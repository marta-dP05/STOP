import socket
import threading
import json


def print_board(board_data):
    print("\n" + "=" * 40)
    print(f"Partida: {board_data['game_id']}")
    print(f"Iniciada: {'Sí' if board_data['started'] else 'No'}")
    print(f"Letra: {board_data['letter'] if board_data['letter'] else '-'}")
    print(f"Jugadores: {', '.join(board_data['players']) if board_data['players'] else '-'}")
    print("-" * 40)

    board = board_data["board"]
    locks = board_data["locks"]

    for category in board:
        value = board[category] if board[category] else "[vacío]"
        locked_by = locks[category]
        if locked_by is None:
            lock_text = ""
        else:
            lock_text = f"  🔒 bloqueado por {locked_by}"

        print(f"{category:<10}: {value}{lock_text}")

    print("=" * 40 + "\n")


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

    elif msg_type == "START":
        print(f"\n[PARTIDA] {data}")

    elif msg_type == "END":
        print(f"\n[FIN] {data}")

    elif msg_type == "BOARD":
        print_board(data)

    else:
        print(f"\n[DESCONOCIDO] {msg}")


def receive_messages(sock):
    buffer = ""

    while True:
        try:
            data = sock.recv(4096)
            if not data:
                break

            buffer += data.decode()

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                handle_message(line)

        except Exception:
            break


HOST = input("IP del servidor: ").strip()
PORT = 8091

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((HOST, PORT))

thread = threading.Thread(target=receive_messages, args=(client,), daemon=True)
thread.start()

while True:
    msg = input("> ")
    client.sendall((msg + "\n").encode())

    if msg == "EXIT":
        break
