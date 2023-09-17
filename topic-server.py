import socket
import threading

HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
PORT = 3333  # Port to listen on (non-privileged ports are > 1023)
SECRET = 'somesecret'


class Request:
    def __init__(self, command, params):
        self.type = command
        self.params = params


class Response:
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload


def serialize(response):
    return bytes(str(response.status) + ' ' + response.payload, encoding='utf-8')


def deserialize(request):
    items = request.decode('utf-8').strip().split(' ')
    if len(items) > 1:
        return Request(items[0], items[1:])
    return Request(items[0], None)


class StateMachine:
    def __init__(self, client, global_state):
        self.transitions = {}
        self.start_state = None
        self.end_states = []
        self.current_state = None
        self.global_state = global_state
        self.client = client

    def add_transition(self, state_name, command, transition, end_state=0):
        self.transitions.setdefault(state_name, {})
        self.transitions[state_name][command] = transition
        if end_state:
            self.end_states.append(state_name)

    def set_start(self, name):
        self.start_state = name
        self.current_state = name

    def process_command(self, unpacked_request):
        print('Starea înainte:', self.current_state)
        handler = self.transitions[self.current_state].get(unpacked_request.type)
        print('Tranziție:', handler)
        if not handler:
            return Response(-4, 'Nu se poate face tranziția din această stare')
        else:
            new_state, response = handler(unpacked_request, self.global_state, self.client)
            self.current_state = new_state
            print('Starea după:', self.current_state)
            return response


class TopicProtocol(StateMachine):
    def __init__(self, client, global_state):
        super().__init__(client, global_state)
        self.set_start('start')  # inițializarea stării de început
        self.add_transition('start', 'connect', request_connect)  # starea de conectare
        self.add_transition('auth', 'disconnect', request_disconnect)  # starea de deconectare
        self.add_transition('auth', 'subscribe', request_subscribe)  # starea de abonare
        self.add_transition('auth', 'unsubscribe', request_unsubscribe)  # starea de dezabonare
        self.add_transition('auth', 'publish', request_publish)  # starea de publicare
        self.add_transition('start', 'nickname', request_nickname)  # starea de introducere a pseudonimului
        self.add_transition('auth', 'help', request_help)  # starea de afișare a informațiilor de ajutor
        self.add_transition('auth', 'users', request_users)  # starea de afișare a utilizatorilor conectați


class TopicList:
    def __init__(self):
        self.clients = []
        self.topics = {}
        self.lock = threading.Lock()

    def add_client(self, client):
        with self.lock:
            self.clients.append(client)

    def remove_client(self, client):
        with self.lock:
            self.clients.remove(client)
            for topic, clients in self.topics.items():
                clients.remove(client)

    def subscribe(self, topic, client):
        with self.lock:
            self.topics.setdefault(topic, [])
            self.topics[topic].append(client)

    def unsubscribe(self, topic, client):
        with self.lock:
            self.topics[topic].remove(client)

    def get_connected_users(self):
        with self.lock:
            return [str(client.getpeername()) for client in self.clients]

    def get_help_info(self):
        help_list = ["help: Show available commands and their descriptions",
                     "quit: Disconnect from the server",
                     "subscribe <topic>: Subscribe to a topic",
                     "unsubscribe <topic>: Unsubscribe from a topic",
                     "publish <topic> <message>: Publish a message to a topic",
                     "publish <topic> upper <mesage>: Publish a upper message to a topic"
        ]
        help_info = "\n✽ ✾ ✿ ❀ ❁ ❃ ❊ ❋ ✣ ✤"
        for i in help_list:
            help_info+="\n✿ "+i
        help_info+="\n✽ ✾ ✿ ❀ ❁ ❃ ❊ ❋ ✣ ✤"
        return help_info


is_running = True
global_state = TopicList()


def handle_client_write(client, response):
    client.sendall(serialize(response))


def handle_client_read(client):
    try:
        protocol = TopicProtocol(client, global_state)
        while True:
            if client is None:
                break
            data = client.recv(1024)
            if not data:
                break
            unpacked_request = deserialize(data)
            response = protocol.process_command(unpacked_request)
            handle_client_write(client, response)

    except OSError as e:
        global_state.remove_client(client)


def request_connect(request, global_state, client):
    if len(request.params) > 0:
        if request.params[0] == SECRET:
            return ('auth', Response(0, 'Ești conectat.'))
        else:
            return ('start', Response(-2, 'Nu cunoști secretul.'))
    else:
        return ('start', Response(-1, 'Nu ai introdus suficiente parametri.'))


def request_disconnect(request, global_state, client):
    return ('start', Response(0, 'Ești deconectat.'))


def request_subscribe(request, global_state, client):
    if len(request.params) > 0:
        global_state.subscribe(request.params[0], client)
        return ('auth', Response(0, f'Ești abonat la {request.params[0]}.'))
    else:
        return ('auth', Response(-1, 'Nu ai introdus suficiente parametri.'))


def request_unsubscribe(request, global_state, client):
    if len(request.params) > 0:
        global_state.unsubscribe(request.params[0], client)
        return ('auth', Response(0, f'Ai dezabonat de la {request.params[0]}.'))
    else:
        return ('auth', Response(-1, 'Nu ai introdus suficiente parametri.'))


def request_publish(request, global_state, client):
    if len(request.params) > 1:
        topic = request.params[0]
        verificUpper = request.params[1]
        data = " ".join(request.params[1:])  # Concatenarea tuturor cuvintelor
        if "upper" == verificUpper:
            transformed_data = data.upper()  # Transformarea întregului text în uppercase
        else:
            transformed_data = " ".join(request.params[0:])

        for c in global_state.topics.get(topic, []):
            if c != client:
                c.sendall(bytes(transformed_data, encoding='utf-8'))

        return ('auth', Response(0, 'Mesajul a fost publicat.'))
    else:
        return ('auth', Response(-1, 'Nu ai introdus suficienți parametri.'))


def request_nickname(request, global_state, client):
    if len(request.params) > 0:
        nickname = request.params[0]
        return ('auth', Response(0, f'Bună, {nickname}!'))
    else:
        return ('auth', Response(-1, 'Nu ai introdus un pseudonim.'))


def request_help(request, global_state, client):
    help_info = global_state.get_help_info()
    return ('auth', Response(0, help_info))


def request_users(request, global_state, client):
    connected_users = global_state.get_connected_users()
    users_info = "Utilizatori conectați:\n" + "\n".join(connected_users)
    return ('auth', Response(0, users_info))


def accept(server):
    while is_running:
        client, addr = server.accept()
        global_state.add_client(client)
        print(f"{addr} s-a conectat")
        client_read_thread = threading.Thread(target=handle_client_read, args=(client,))
        client_read_thread.start()


def main():
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((HOST, PORT))
        server.listen()
        accept_thread = threading.Thread(target=accept, args=(server,))
        accept_thread.start()
        accept_thread.join()
    except BaseException as err:
        print(err)
    finally:
        if server:
            server.close()


if __name__ == '__main__':
    main()