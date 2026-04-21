import socket
import threading


def receive_messages(sock):
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                break
            print(data.decode(), end="")
        except:
            break


HOST = input("IP del servidor: ").strip()
PORT = 8091

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((HOST, PORT))

thread = threading.Thread(target=receive_messages, args=(client,), daemon=True)
thread.start()

while True:
    msg = input()
    client.sendall((msg + "\n").encode())

    if msg == "EXIT":
        break
