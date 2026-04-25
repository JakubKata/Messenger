import socket
import ssl
import threading
import json
import os
from database import init_db, get_client, new_client, offline_message_save, offline_message_read, is_existing_client,get_ready_clients, get_all_clients, update_public_key, get_public_key
from protocol import CMD_MSG, CMD_CLIENTS, CMD_ACK, CMD_NACK, CMD_SAVE, CMD_NEW, CMD_EXISTING, CMD_BUSY, CMD_ACTIVE, CMD_ALL, CMD_PUBKEY, CMD_GETKEY, CMD_KEY
from dotenv import load_dotenv

#.env
load_dotenv()
ip = os.getenv("SERVER_IP")
port = int(os.getenv("SERVER_PORT"))
key = os.getenv("SECRET_KEY")

#.jsom
with open("config.json", "r",encoding="utf-8") as f:
    config = json.load(f)

#tls
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(certfile="server.crt", keyfile="server.key")

init_db()
active_clients = {} #active_client = {client_id : [client_socket, client_address, name, password]}

def get_active_clients():
    active_clients_text = ""
    for id in active_clients:
        active_clients_text += f"{id}, {active_clients[id][2]} |"
    return active_clients_text

def authenticate_key(client_socket, client_address): 
    client_key = client_socket.recv(1024).decode().strip()
    if client_key != key:
        client_socket.send(f"{CMD_NACK}\n".encode())
        return False
    else:
        client_socket.send(f"{CMD_ACK}\n".encode())
        return True
       
def authenticate(client_socket, client_address):
    while True:
        mode = client_socket.recv(1024).decode().strip()
        if mode == CMD_NEW:
            client_id = client_socket.recv(1024).decode().strip()
            if not client_id:
                client_socket.send(f"{CMD_NACK}\n".encode())
                return False

            if is_existing_client(client_id):
                client_socket.send(f"{CMD_BUSY}\n".encode())
                continue
            else:
                client_socket.send(f"{CMD_ACK}\n".encode())
                response = client_socket.recv(1024).decode().strip()
                if not response or "|" not in response:
                    return False
                name, password = response.split("|", 1)
                new_client(client_id, name, password)
                active_clients[client_id] = [client_socket, client_address, name, password] #active_client = {client_id : [client_socket, client_address, name, password]}
                client_socket.send(f"{CMD_ACK}\n".encode())
                return client_id
            
        elif mode == CMD_EXISTING:
            response = client_socket.recv(1024).decode().strip()
            if not response or "|" not in response:
                client_socket.send(f"{CMD_NACK}\n".encode())
                continue

            client_id, client_password = response.split("|", 1)
            if not is_existing_client(client_id):
                client_socket.send(f"{CMD_NACK}\n".encode())
                continue

            client = get_client(client_id)
            password = client[1]
            if password != client_password:
                client_socket.send(f"{CMD_NACK}\n".encode())
                continue

            active_clients[client_id] = [client_socket, client_address, *client] #active_client = {client_id : [client_socket, client_address, name, password]}
            name = active_clients[client_id][2]
            client_socket.send(f"{CMD_ACK}|{name}\n".encode()) 
            return client_id
        else:
            client_socket.send(f"{CMD_NACK}\n".encode())
            return False
            
def do_clients(client_socket, parts):
    if parts[1] == CMD_ACTIVE:
        clients_text = get_active_clients()
        client_socket.send(f"{clients_text}\n".encode())
    elif parts[1] == CMD_ALL:
        clients_text = get_ready_clients()
        client_socket.send(f"{clients_text}\n".encode())

def do_public_key(client_socket, client_id, parts):
    public_key = parts[1]
    update_public_key(client_id, public_key)
    client_socket.send(f"{CMD_ACK}|{CMD_KEY}\n".encode())

def do_get_key(client_socket, parts):
    target_id = parts[1]
    public_key = get_public_key(target_id)
    if public_key != None:
        client_socket.send(f"{CMD_PUBKEY}|{target_id}|{public_key}\n".encode())
    else:
        client_socket.send(f"{CMD_ACK}|{CMD_NACK}\n".encode())

def do_message(client_socket, client_id, parts):
    destination_id = parts[1]
    message = parts[2]
    sender_name = active_clients[client_id][2]
    if destination_id in active_clients:
        active_clients[destination_id][0].send(f"{CMD_MSG}|{client_id}|{sender_name}|{message}\n".encode())
        client_socket.send(f"{CMD_ACK}|{CMD_ACK}\n".encode())
    else:
        if is_existing_client(destination_id):
            client_socket.send(f"{CMD_ACK}|{CMD_SAVE}\n".encode())
            sender_name = active_clients[client_id][2]
            offline_message_save(destination_id, client_id, sender_name, message)
        else:                       
            client_socket.send(f"{CMD_ACK}|{CMD_NACK}\n".encode())

def handle_client(client_socket, client_address):
    client_id = None
    try:
        if authenticate_key(client_socket, client_address) == False:
            return

        client_id = authenticate(client_socket, client_address)
        if not client_id:
            return

        offline_data = offline_message_read(client_id)
        if offline_data != None:
            client_socket.send(offline_data.encode())

        while True:
            data = client_socket.recv(8192).decode()
            if not data:
                break

            messages = data.split("\n")
            for response in messages:
                if not response.strip(): 
                    continue

                parts = response.split("|")
                command = parts[0]
                if command == CMD_CLIENTS:
                    do_clients(client_socket, parts)
                    continue
                
                if command == CMD_PUBKEY:
                    do_public_key(client_socket, client_id, parts)
                    continue

                if command == CMD_GETKEY:
                    do_get_key(client_socket, parts)
                    continue

                if command == CMD_MSG:
                    do_message(client_socket, client_id, parts)
                    continue
    except (ConnectionResetError, ssl.SSLError) as e:
        print(f"Connection error for client {client_id}: {e}")
    except Exception as e:
        print(f"Error handling client {client_id}: {e}")
    finally:
        if client_id:
            active_clients.pop(client_id, None)
        client_socket.close()


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_socket.bind((ip, port))
    except OSError as e:
        print(f"Bind error: {e}")
        exit(1)
        
    server_socket.listen()

    print(f"server is listening to {ip}:{port}...")
     
    while True:
        client_socket, client_address = server_socket.accept()

        try:
            secure_socket = context.wrap_socket(client_socket, server_side=True)
        except ssl.SSLError:
            client_socket.close()
            continue

        if len(active_clients) >= int(config["MAX_CLIENTS"]):
            secure_socket.close()
            continue
        
        threading.Thread(target=handle_client, args=(secure_socket, client_address), daemon=True).start()