#database.py
import sqlite3
from protocol import CMD_MSG

def init_db():
    conn = sqlite3.connect("clients.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            client_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            password TEXT NOT NULL,
            offline_messages TEXT
        )""")
    conn.commit()
    conn.close()

def get_client(client_id):
    conn = sqlite3.connect("clients.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, password FROM users WHERE client_id = ?", (client_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def new_client(client_id, name, password):
    conn = sqlite3.connect("clients.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (client_id, name, password) VALUES (?, ?, ?)", (client_id, name, password))
    conn.commit()
    conn.close()

def is_existing_client(client_id):
    if get_client(client_id) == None:
        return False
    else:
        return True

def offline_message_read(client_id):
    conn = sqlite3.connect("clients.db")
    cursor = conn.cursor()
    cursor.execute("SELECT offline_messages FROM users WHERE client_id = ?", (client_id,))
    result = cursor.fetchone()
    cursor.execute("UPDATE users SET offline_messages = NULL WHERE client_id = ?", (client_id,))
    conn.commit()
    conn.close()
    return result

def offline_message_save(destination_id, client_id, sender_name, message):
    conn = sqlite3.connect("clients.db")
    cursor = conn.cursor()
    cursor.execute("SELECT offline_messages FROM users WHERE client_id = ?", (destination_id,))
    result = cursor.fetchone()
    if result[0] == None:
        new_offline_message = f"{CMD_MSG}|{client_id}|{sender_name}|{message}\n"
    else:
        new_offline_message = result[0] + f"{CMD_MSG}|{client_id}|{sender_name}|{message}\n"
    cursor.execute("UPDATE users SET offline_messages = ? WHERE client_id = ?", (new_offline_message, destination_id))
    conn.commit()
    conn.close()

def get_all_clients():
    conn = sqlite3.connect("clients.db")
    cursor = conn.cursor()
    cursor.execute("SELECT client_id, name FROM users")
    result = cursor.fetchall()
    conn.close()
    all_clients_text = ""
    for r in result:
        all_clients_text += f"{r[0]}, {r[1]} |"
    return all_clients_text
