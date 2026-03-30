import socket
import threading
import os
from dotenv import load_dotenv

#.env
load_dotenv()
ip = os.getenv("SERVER_IP")
port = int(os.getenv("SERVER_PORT"))
key = os.getenv("SECRET_KEY")

#functions
def receive_messages(client_socket):
    while True:
        message = client_socket.recv(4096).decode()
        if not message:
            break
        parts = message.split("|")
        command = parts[0]
        
        if command == "ACK":
            if parts[1] == "ACK":
                print("Message sent successfully.")
            elif parts[1] == "NACK":
                print("Failed to send the message. The destination client is not active.")
        elif command == "MSG":
            print(f"Message from id:{parts[1]} name:{parts[2]}: {parts[3]}")
        else:    
            print(message)

def send_message(client_socket):
    while True:
        destination_id = input("Enter the destination client ID (or 'ACTIVE' to see active clients): ")
        if destination_id == "ACTIVE":
            client_socket.send("ACTIVE".encode())
            continue
        message = input("Enter your message: ")
        client_socket.send(f"MSG|{destination_id}|{message}".encode())
        

def authenticate(client_socket):
    client_socket.send(key.encode())
    if "NACK" == client_socket.recv(1024).decode():
        return False
    elif "ACK" == client_socket.recv(1024).decode():
        client_id = input("Enter your client ID: ")
        client_socket.send(client_id.encode())
        response = client_socket.recv(1024).decode()

        if response == "NEW":
            name = input("Enter your NEW name: ")
            password = input("Enter your NEW password: ")
            client_socket.send(f"{name}|{password}".encode())
        else:
            password = input("Enter your password: ")
            client_socket.send(password.encode())
        
        response = client_socket.recv(1024).decode()
        if response.split("|")[0] == "ACK":
            name = response.split("|")[1]
            return True
        else:
            print("Authentication failed.")
            return False
            
while True:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect((ip, port))

        if authenticate(client_socket):            
            threading.Thread(target=receive_messages, args=(client_socket,), daemon=True).start()
            send_message(client_socket)
        else:
            client_socket.close()