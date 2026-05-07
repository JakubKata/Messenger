import socket
import ssl
import threading
import json
import os

from database import Database
from protocol import Packet, CMD_MSG, CMD_CLIENTS, CMD_ACK, CMD_NACK, CMD_SAVE, CMD_NEW, CMD_EXISTING, CMD_BUSY, CMD_ACTIVE, CMD_ALL, CMD_PUBKEY, CMD_GETKEY, CMD_KEY
from dotenv import load_dotenv

class ChatServer:
    def __init__(self):
        load_dotenv()
        self.ip = os.getenv("SERVER_IP")
        self.port = int(os.getenv("SERVER_PORT"))
        self.key = os.getenv("SECRET_KEY")

        with open("config.json", "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(certfile="server.crt", keyfile="server.key")

        self.database = Database()
        self.database.init_db()
        self.active_clients = {}  # active_client = {client_id : [client_socket, client_address, name, password]}

    def get_active_clients(self):
        active_clients_text = ""
        for id in self.active_clients:
            active_clients_text += f"{id}, {self.active_clients[id][2]} |"
        return active_clients_text

    def authenticate_key(self, client_socket, client_address):
        client_key = client_socket.recv(1024).decode().strip()
        if client_key != self.key:
            client_socket.sendall(Packet(CMD_NACK).encode())
            return False
        else:
            client_socket.sendall(Packet(CMD_ACK).encode())
            return True

    def authenticate(self, client_socket, client_address):
        while True:
            raw_mode = client_socket.recv(1024).decode().strip()
            if not raw_mode:
                client_socket.sendall(Packet(CMD_NACK).encode())
                return False

            mode_packet = Packet.decode(raw_mode)

            if mode_packet.command == CMD_NEW:
                if len(mode_packet.args) < 1:
                    client_socket.sendall(Packet(CMD_NACK).encode())
                    return False

                client_id = mode_packet.args[0]

                if self.database.is_existing_client(client_id):
                    client_socket.sendall(Packet(CMD_BUSY).encode())
                    continue
                else:
                    client_socket.sendall(Packet(CMD_ACK).encode())
                    response = client_socket.recv(1024).decode().strip()
                    if not response:
                        return False
                    response_packet = Packet.decode(response)
                    if response_packet.command != CMD_NEW or len(response_packet.args) < 2:
                        return False
                    name, password = response_packet.args[0], response_packet.args[1]
                    self.database.new_client(client_id, name, password)
                    self.active_clients[client_id] = [client_socket, client_address, name, password]  # active_client = {client_id : [client_socket, client_address, name, password]}
                    client_socket.sendall(Packet(CMD_ACK).encode())
                    return client_id

            elif mode_packet.command == CMD_EXISTING:
                if len(mode_packet.args) < 2:
                    client_socket.sendall(Packet(CMD_NACK).encode())
                    continue

                client_id, client_password = mode_packet.args[0], mode_packet.args[1]
                if not self.database.is_existing_client(client_id):
                    client_socket.sendall(Packet(CMD_NACK).encode())
                    continue

                client = self.database.get_client(client_id)
                password = client[1]
                if password != client_password:
                    client_socket.sendall(Packet(CMD_NACK).encode())
                    continue

                self.active_clients[client_id] = [client_socket, client_address, *client]  # active_client = {client_id : [client_socket, client_address, name, password]}
                name = self.active_clients[client_id][2]
                client_socket.sendall(Packet(CMD_ACK, name).encode())
                return client_id
            else:
                client_socket.sendall(Packet(CMD_NACK).encode())
                return False

    def do_clients(self, client_socket, parts):
        if parts[1] == CMD_ACTIVE:
            clients_text = self.get_active_clients()
            client_socket.sendall(Packet(CMD_ACTIVE, clients_text).encode())
        elif parts[1] == CMD_ALL:
            clients_text = self.database.get_ready_clients()
            client_socket.sendall(Packet(CMD_ALL, clients_text).encode())

    def do_public_key(self, client_socket, client_id, parts):
        if len(parts) < 2:
            client_socket.sendall(Packet(CMD_ACK, CMD_NACK).encode())
            return
        public_key = parts[1]
        self.database.update_public_key(client_id, public_key)
        client_socket.sendall(Packet(CMD_ACK, CMD_KEY).encode())

    def do_get_key(self, client_socket, parts):
        if len(parts) < 2:
            client_socket.sendall(Packet(CMD_ACK, CMD_NACK).encode())
            return
        target_id = parts[1]
        public_key = self.database.get_public_key(target_id)
        if public_key != None:
            client_socket.sendall(Packet(CMD_PUBKEY, target_id, public_key).encode())
        else:
            client_socket.sendall(Packet(CMD_ACK, CMD_NACK).encode())

    def do_message(self, client_socket, client_id, parts):
        if len(parts) < 3:
            client_socket.sendall(Packet(CMD_ACK, CMD_NACK).encode())
            return
        destination_id = parts[1]
        message = "|".join(parts[2:])
        sender_name = self.active_clients[client_id][2]
        if destination_id in self.active_clients:
            self.active_clients[destination_id][0].sendall(Packet(CMD_MSG, client_id, sender_name, message).encode())
            client_socket.sendall(Packet(CMD_ACK, CMD_ACK).encode())
        else:
            if self.database.is_existing_client(destination_id):
                client_socket.sendall(Packet(CMD_ACK, CMD_SAVE).encode())
                sender_name = self.active_clients[client_id][2]
                self.database.offline_message_save(destination_id, client_id, sender_name, message)
            else:
                client_socket.sendall(Packet(CMD_ACK, CMD_NACK).encode())

    def handle_client(self, client_socket, client_address):
        client_id = None
        try:
            if self.authenticate_key(client_socket, client_address) == False:
                return

            client_id = self.authenticate(client_socket, client_address)
            if not client_id:
                return

            offline_data = self.database.offline_message_read(client_id)
            if offline_data != None:
                client_socket.sendall(offline_data.encode())

            buffer = ""
            while True:
                data = client_socket.recv(8192).decode()
                if not data:
                    break

                buffer += data
                messages = buffer.split("\n")
                buffer = messages.pop()
                for response in messages:
                    if not response.strip():
                        continue

                    parts = response.split("|")
                    command = parts[0]
                    if command == CMD_CLIENTS:
                        if len(parts) < 2:
                            client_socket.sendall(Packet(CMD_ACK, CMD_NACK).encode())
                            continue
                        self.do_clients(client_socket, parts)
                        continue

                    if command == CMD_PUBKEY:
                        self.do_public_key(client_socket, client_id, parts)
                        continue

                    if command == CMD_GETKEY:
                        self.do_get_key(client_socket, parts)
                        continue

                    if command == CMD_MSG:
                        self.do_message(client_socket, client_id, parts)
                        continue

                    client_socket.sendall(Packet(CMD_ACK, CMD_NACK).encode())
        except (ConnectionResetError, ssl.SSLError) as e:
            print(f"Connection error for client {client_id}: {e}")
        except Exception as e:
            print(f"Error handling client {client_id}: {e}")
        finally:
            if client_id:
                self.active_clients.pop(client_id, None)
            client_socket.close()

    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                server_socket.bind((self.ip, self.port))
            except OSError as e:
                print(f"Bind error: {e}")
                exit(1)

            server_socket.listen()

            print(f"server is listening to {self.ip}:{self.port}...")

            while True:
                client_socket, client_address = server_socket.accept()

                try:
                    secure_socket = self.context.wrap_socket(client_socket, server_side=True)
                except ssl.SSLError:
                    client_socket.close()
                    continue

                if len(self.active_clients) >= int(self.config["MAX_CLIENTS"]):
                    secure_socket.close()
                    continue

                threading.Thread(target=self.handle_client, args=(secure_socket, client_address), daemon=True).start()


if __name__ == "__main__":
    ChatServer().run()