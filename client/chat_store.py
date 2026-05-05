class ChatStore:
    def __init__(self):
        self.users = {}
        self.history = {}

    def add_message(self, target_id, direction, author, text):
        if target_id not in self.history:
            self.history[target_id] = []
        self.history[target_id].append((direction, author, text))

    def get_messages(self, user_id):
        return self.history.get(user_id, [])

    def update_user_status(self, user_id, is_online, name=None, has_unread=None, last_active=None):
        if user_id not in self.users:
            self.users[user_id] = {
                "name": "",
                "is_online": False,
                "has_unread": False,
                "last_active": 0,
            }

        self.users[user_id]["is_online"] = is_online

        if name is not None:
            self.users[user_id]["name"] = name
        if has_unread is not None:
            self.users[user_id]["has_unread"] = has_unread
        if last_active is not None:
            self.users[user_id]["last_active"] = last_active

        return self.users[user_id]