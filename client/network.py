import os
import socket
import ssl
import rsa
from dotenv import load_dotenv
from PySide6.QtCore import QThread, Signal

from crypto_manager import CryptoManager
from protocol import Packet
from protocol import CMD_MSG, CMD_CLIENTS, CMD_ACK, CMD_NACK, CMD_SAVE, CMD_NEW, CMD_EXISTING, CMD_BUSY, CMD_ACTIVE, CMD_ALL, CMD_PUBKEY, CMD_GETKEY, CMD_KEY

class NetworkClient(QThread):
    signal_login_ok = Signal(str)
    signal_login_fail = Signal(str)
    signal_new_msg = Signal(str, str, str)
    signal_clients_list = Signal(str, str)
    signal_system_msg = Signal(str)

    def __init__(self):
        super().__init__()

        load_dotenv()
        self.ip = os.getenv("SERVER_IP")
        self.port = int(os.getenv("SERVER_PORT"))
        self.key = os.getenv("SECRET_KEY")

        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.context.load_verify_locations("server.crt")
        self.context.check_hostname = False

        self.socket = None
        self.client_id = None
        self.crypto_manager = None
        self.private_key = None
        self.public_key = None
        self.cached_public_key = {}
        self.pending_public_keys = set()
        self._recv_buffer = ""
        self._intentional_disconnect = False
        self.is_running = True

    def close_connection(self):
        self._intentional_disconnect = True
        self.is_running = False

        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.socket.close()
            except OSError:
                pass
            self.socket = None

        if self.isRunning():
            self.wait(1500)

        self.pending_public_keys.clear()
        self._recv_buffer = ""

    def _recv_line(self):
        while "\n" not in self._recv_buffer:
            chunk = self.socket.recv(4096).decode()
            if not chunk:
                return None
            self._recv_buffer += chunk

        line, self._recv_buffer = self._recv_buffer.split("\n", 1)
        return line.strip()

    def connect_to_server(self):
        try:
            self.is_running = True
            self._intentional_disconnect = False
            self._recv_buffer = ""
            self.pending_public_keys.clear()

            if self.socket:
                try:
                    self.socket.close()
                except OSError:
                    pass

            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket = self.context.wrap_socket(client_socket, server_hostname=self.ip)
            self.socket.connect((self.ip, self.port))
            return True
        except ConnectionRefusedError as e:
            self.signal_system_msg.emit(f"Connection error: {e}")
            return False
        except socket.gaierror as e:
            self.signal_system_msg.emit(f"Address error: {e}")
            return False
        except Exception as e:
            self.signal_system_msg.emit(f"Unexpected error: {e}")
            return False

    def authenticate_existing(self, client_id, password):
        if not self.connect_to_server():
            self.signal_login_fail.emit("Failed to connect to server.")
            return False

        self.socket.sendall(f"{self.key}\n".encode())
        authentication_response = self._recv_line()

        if authentication_response == CMD_NACK:
            self.signal_login_fail.emit("Invalid server key.")
            return False

        if authentication_response == CMD_ACK:
            self.socket.sendall(Packet(CMD_EXISTING, client_id, password).encode())
            response = self._recv_line()

            if response is None:
                self.signal_login_fail.emit("Connection closed during login.")
                return False

            if response.startswith(f"{CMD_ACK}|") or response == CMD_ACK:
                self.client_id = client_id
                self.crypto_manager = CryptoManager(client_id)
                self.private_key = self.crypto_manager.private_key
                self.public_key = self.crypto_manager.public_key
                public_key_str = self.public_key.save_pkcs1().decode().replace("\n", "~")
                self.socket.sendall(Packet(CMD_PUBKEY, public_key_str).encode())

                self.signal_login_ok.emit(client_id)
                if not self.isRunning():
                    self.start()
                return True

            if response == CMD_NACK:
                self.signal_login_fail.emit("Invalid client ID or password. Please try again.")
                return False

        self.signal_login_fail.emit("Authentication failed.")
        return False

    def authenticate_new(self, client_id, name, password):
        if not self.connect_to_server():
            self.signal_login_fail.emit("Failed to connect to server.")
            return False

        self.socket.sendall(f"{self.key}\n".encode())
        authentication_response = self._recv_line()

        if authentication_response == CMD_NACK:
            self.signal_login_fail.emit("Invalid server key.")
            return False

        if authentication_response == CMD_ACK:
            self.socket.sendall(Packet(CMD_NEW, client_id).encode())
            response = self._recv_line()

            if response is None:
                self.signal_login_fail.emit("Connection closed during registration.")
                return False

            if response == CMD_BUSY:
                self.signal_login_fail.emit("Client ID is already in use. Please choose a different one.")
                return False

            if response == CMD_ACK:
                self.socket.sendall(Packet(CMD_NEW, name, password).encode())
                register_response = self._recv_line()
                if register_response == CMD_ACK:
                    self.client_id = client_id
                    self.crypto_manager = CryptoManager(client_id)
                    self.private_key = self.crypto_manager.private_key
                    self.public_key = self.crypto_manager.public_key
                    public_key_str = self.public_key.save_pkcs1().decode().replace("\n", "~")
                    self.socket.sendall(Packet(CMD_PUBKEY, public_key_str).encode())

                    self.signal_login_ok.emit(client_id)
                    if not self.isRunning():
                        self.start()
                    return True

        self.signal_login_fail.emit("Authentication failed.")
        return False

    def request_clients(self, cmd_type):
        if self.socket:
            try:
                self.socket.sendall(Packet(CMD_CLIENTS, cmd_type).encode())
            except OSError as e:
                self.signal_system_msg.emit(f"Connection error: {e}")

    def request_public_key(self, target_id, notify=False):
        if not self.socket or not target_id:
            return False
        if target_id in self.cached_public_key or target_id in self.pending_public_keys:
            return True
        try:
            self.socket.sendall(Packet(CMD_GETKEY, target_id).encode())
            self.pending_public_keys.add(target_id)
            if notify:
                self.signal_system_msg.emit(f"Fetching key for {target_id}... Please wait a moment and send again.")
            return True
        except OSError as e:
            self.signal_system_msg.emit(f"Connection error: {e}")
            return False

    def send_chat_message(self, destination_id, message):
        if not self.socket:
            self.signal_system_msg.emit("Not connected to server.")
            return

        if destination_id not in self.cached_public_key:
            self.request_public_key(destination_id, notify=True)
            return

        public_key = self.cached_public_key[destination_id]
        try:
            encrypted_msg = self.crypto_manager.encrypt(message, public_key)
            self.socket.sendall(Packet(CMD_MSG, destination_id, encrypted_msg).encode())
        except Exception as e:
            self.signal_system_msg.emit(f"Encryption error: {e}")

    def run(self):
        buffer = self._recv_buffer
        self._recv_buffer = ""
        while self.is_running and self.socket:
            try:
                data = self.socket.recv(8192).decode()
                if not data:
                    break
            except (ConnectionResetError, ssl.SSLError, OSError) as e:
                if not self._intentional_disconnect:
                    self.signal_system_msg.emit(f"Connection lost: {e}")
                break

            buffer += data
            messages = buffer.split("\n")
            buffer = messages.pop()
            for message in messages:
                if not message.strip():
                    continue
                packet = Packet.decode(message)
                command = packet.command
                parts = [packet.command, *packet.args]

                if command == CMD_ACK:
                    if len(parts) < 2:
                        self.signal_system_msg.emit("Server response was malformed.")
                        continue
                    if parts[1] == CMD_ACK:
                        self.signal_system_msg.emit("Message sent successfully.")
                    elif parts[1] == CMD_SAVE:
                        self.signal_system_msg.emit("The destination client is offline. The message will be saved and delivered when the client comes online.")
                    elif parts[1] == CMD_NACK:
                        self.signal_system_msg.emit("Failed to send the message. The destination client is not existing.")
                    elif parts[1] == CMD_KEY:
                        self.signal_system_msg.emit("The key is in the database.")

                elif command == CMD_MSG:
                    if len(parts) < 4:
                        self.signal_system_msg.emit("Incoming message was malformed.")
                        continue
                    sender_id = parts[1]
                    sender_name = parts[2]
                    encrypted_hex = "|".join(parts[3:])
                    try:
                        decrypted_msg = self.crypto_manager.decrypt(encrypted_hex)
                        self.signal_new_msg.emit(sender_id, sender_name, decrypted_msg)
                    except Exception:
                        self.signal_system_msg.emit("invalid private key")

                elif command == CMD_PUBKEY:
                    if len(parts) < 3:
                        self.signal_system_msg.emit("Received malformed public key response.")
                        continue
                    target_id = parts[1]
                    public_key = parts[2].replace("~", "\n")
                    self.cached_public_key[target_id] = rsa.PublicKey.load_pkcs1(public_key.encode())
                    self.pending_public_keys.discard(target_id)
                    self.signal_system_msg.emit(f"Received public key for client: {target_id}")

                elif command in [CMD_ALL, CMD_ACTIVE]:
                    clients_text = "|".join(parts[1:])
                    self.signal_clients_list.emit(command, clients_text)

                else:
                    self.signal_system_msg.emit(message)

        self.socket = None
        self._intentional_disconnect = False