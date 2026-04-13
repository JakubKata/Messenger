import socket
import ssl
import rsa
import threading
import os
from dotenv import load_dotenv
from protocol import CMD_MSG, CMD_CLIENTS, CMD_ACK, CMD_NACK, CMD_SAVE, CMD_NEW, CMD_ACTIVE, CMD_ALL, CMD_PUBKEY, CMD_GETKEY, CMD_KEY
from dotenv import load_dotenv

#.env
load_dotenv()
ip = os.getenv("SERVER_IP")
port = int(os.getenv("SERVER_PORT"))
key = os.getenv("SECRET_KEY")

#tls
context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.load_verify_locations("server.crt")
context.check_hostname = False 

cached_public_key = {}

#rsa
def get_or_generate_keys(client_id):
    private_file = f"private_{client_id}.pem"
    public_file = f"public_{client_id}.pem"

    if os.path.exists(private_file):
        with open(private_file, "rb") as f:
            private_key = rsa.PrivateKey.load_pkcs1(f.read())
        with open(public_file, "rb") as f:
            public_key = rsa.PublicKey.load_pkcs1(f.read())
    else:
        public_key, private_key = rsa.newkeys(4096)
        with open(private_file, "wb") as f:
            f.write(private_key.save_pkcs1())
        with open(public_file, "wb") as f:
            f.write(public_key.save_pkcs1())
    return public_key, private_key

#functions
def receive_messages(client_socket, private_key):
    while True:
        data = client_socket.recv(8192).decode()
        if not data:
            break

        messages = data.strip().split("\n")
        for message in messages:
            if not message.strip():
                continue
            parts = message.split("|")
            command = parts[0]
            
            if command == CMD_ACK:
                if parts[1] == CMD_ACK:
                    print("Message sent successfully.")
                elif parts[1] == CMD_SAVE:
                    print("The destination client is offline. The message will be saved and delivered when the client comes online.")
                elif parts[1] == CMD_NACK:
                    print("Failed to send the message. The destination client is not existing.")
                elif parts[1] == CMD_KEY:
                    print("The key is in the database")

            elif command == CMD_MSG:
                sender_id = parts[1]
                sender_name = parts[2]
                encrypted_hex = parts[3]
                try:
                    encrypted_bytes = bytes.fromhex(encrypted_hex)
                    decrypted_msg = rsa.decrypt(encrypted_bytes, private_key).decode()
                    print(f"Message from id:{sender_id} name:{sender_name}: {decrypted_msg}")
                except Exception as e:
                    print("invalid private key")

            elif command == CMD_PUBKEY:
                target_id = parts[1]
                public_key = parts[2].replace("~", "\n")
                cached_public_key[target_id] = rsa.PublicKey.load_pkcs1(public_key.encode())

            else:    
                print(message)
                

def send_message(client_socket):
    while True:
        destination_id = input("Enter the destination client ID (ALL or 'ACTIVE' to see active clients): ")
        if destination_id == CMD_ACTIVE:
            client_socket.send(f"{CMD_CLIENTS}|{CMD_ACTIVE}\n".encode())
            continue

        if destination_id == CMD_ALL:
            client_socket.send(f"{CMD_CLIENTS}|{CMD_ALL}\n".encode())
            continue

        if destination_id not in cached_public_key:
            client_socket.send(f"{CMD_GETKEY}|{destination_id}\n".encode())
            continue

        message = input("Enter your message: ")
        public_key = cached_public_key[destination_id]
        encrypted_msg = rsa.encrypt(message.encode(), public_key).hex()
        client_socket.send(f"{CMD_MSG}|{destination_id}|{encrypted_msg}\n".encode())
        

def authenticate(client_socket):
    client_socket.send(f"{key}\n".encode())
    authention_response = client_socket.recv(1024).decode().strip()
    if CMD_NACK == authention_response:
        return False
    elif CMD_ACK == authention_response:
        client_id = input("Enter your client ID: ")
        client_socket.send(f"{client_id}\n".encode())
        response = client_socket.recv(1024).decode().strip()

        if response == CMD_NEW:
            name = input("Enter your new name: ")
            password = input("Enter your new password: ")
            client_socket.send(f"{name}|{password}\n".encode())
        else:
            password = input("Enter your password: ")
            client_socket.send(f"{password}\n".encode())
        
        response = client_socket.recv(1024).decode().strip()
        if response.split("|")[0] == CMD_ACK:
            name = response.split("|")[1]
            return client_id
        else:
            print("Authentication failed.")
            return False
            
while True:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        try:
            secure_socket = context.wrap_socket(client_socket, server_hostname=ip)
            secure_socket.connect((ip, port))
        except ConnectionRefusedError as e:
            print(f"Connection error: {e}")
            break
        except socket.gaierror as e:
            print(f"Address error: {e}")
            break
        
        client_id = authenticate(secure_socket) 

        if client_id:
            public_key, private_key = get_or_generate_keys(client_id)
            public_key_str = public_key.save_pkcs1().decode().replace("\n", "~")
            secure_socket.send(f"{CMD_PUBKEY}|{public_key_str}\n".encode())

            threading.Thread(target=receive_messages, args=(secure_socket, private_key), daemon=True).start()
            send_message(secure_socket)
        else:
            secure_socket.close()