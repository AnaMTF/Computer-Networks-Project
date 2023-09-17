import socket
import threading
import queue

HOST = "127.0.0.1"  # Adresa IP sau numele de gazdă al serverului
PORT = 3333  # Portul utilizat de server


def handle_server_write(s, response_queue):
    while True:
        try:
            data = s.recv(1024)
            if not data:
                break
            response_queue.put(data.decode())
        except Exception as e:
            print("Eroare de conexiune:", str(e))
            response_queue.put("ERROR")  # Semnalează o eroare de conexiune către firul principal
            break



def handle_user_input(s):
    nickname = input("Introdu pseudonimul: ")
    s.sendall(f"nickname {nickname}".encode())  # Trimite comanda "nickname" cu pseudonimul

    while True:
        line = input('>')
        if line.strip().lower() == "quit":
            break

        s.sendall(line.encode())


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    response_queue = queue.Queue()

    server_write_thread = threading.Thread(target=handle_server_write, args=(s, response_queue))
    server_write_thread.start()

    user_input_thread = threading.Thread(target=handle_user_input, args=(s,))
    user_input_thread.start()

    while True:
        try:
            response = response_queue.get(timeout=0.1)
            if response == "ERROR":
                # Eroare de conexiune, ieși din bucla while și întrerupe firul de intrare al utilizatorului
                break

            split_response = response.split(' ', 1)
            if len(split_response) == 2:
                status, payload = split_response
                if status.isdigit() and int(status) != 0:
                    print("Error:", payload)
                else:
                    print("Response:", payload)
            else:
                print("Error: Invalid response format. Response:", response)

        except queue.Empty:
            pass

    server_write_thread.join()
    user_input_thread.join()