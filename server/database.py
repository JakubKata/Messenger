# database.py
import sqlite3

from protocol import CMD_MSG


class Database:
    def __init__(self, db_path="clients.db"):
        self.db_path = db_path

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                client_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                password TEXT NOT NULL,
                public_key TEXT,
                offline_messages TEXT
            )""")
        conn.commit()
        conn.close()

    def get_client(self, client_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT name, password FROM users WHERE client_id = ?", (client_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    def new_client(self, client_id, name, password):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (client_id, name, password) VALUES (?, ?, ?)", (client_id, name, password))
        conn.commit()
        conn.close()

    def is_existing_client(self, client_id):
        if self.get_client(client_id) == None:
            return False
        else:
            return True

    def update_public_key(self, client_id, pubkey):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET public_key = ? WHERE client_id = ?", (pubkey, client_id))
        conn.commit()
        conn.close()

    def get_public_key(self, client_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT public_key FROM users WHERE client_id = ?", (client_id,))
        result = cursor.fetchone()
        conn.close()
        if result == None:
            return None
        else:
            return result[0]

    def offline_message_read(self, client_id):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT offline_messages FROM users WHERE client_id = ?", (client_id,))
        result = cursor.fetchone()
        cursor.execute("UPDATE users SET offline_messages = NULL WHERE client_id = ?", (client_id,))
        conn.commit()
        conn.close()
        if result == None:
            return None
        else:
            return result[0]

    def offline_message_save(self, destination_id, client_id, sender_name, message):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT offline_messages FROM users WHERE client_id = ?", (destination_id,))
        result = cursor.fetchone()
        if result == None:
            conn.commit()
            conn.close()
            return
        if result[0] == None:
            new_offline_message = f"{CMD_MSG}|{client_id}|{sender_name}|{message}\n"
        else:
            new_offline_message = result[0] + f"{CMD_MSG}|{client_id}|{sender_name}|{message}\n"
        cursor.execute("UPDATE users SET offline_messages = ? WHERE client_id = ?", (new_offline_message, destination_id))
        conn.commit()
        conn.close()

    def get_all_clients(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT client_id, name FROM users")
        result = cursor.fetchall()
        conn.close()
        all_clients_text = ""
        for r in result:
            all_clients_text += f"{r[0]}, {r[1]} |"
        return all_clients_text

    def get_ready_clients(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT client_id, name FROM users WHERE public_key IS NOT NULL AND password IS NOT NULL AND name IS NOT NULL")
        result = cursor.fetchall()
        conn.close()
        ready_clients_text = ""
        for r in result:
            ready_clients_text += f"{r[0]}, {r[1]} |"
        return ready_clients_text