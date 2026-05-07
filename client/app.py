import sys
import time
from PySide6.QtWidgets import QApplication, QMainWindow, QListWidgetItem, QMessageBox
from PySide6.QtCore import Qt, QTimer
from ui_chat import Ui_MainWindow

from network import NetworkClient
from chat_store import ChatStore
from protocol import CMD_ALL, CMD_ACTIVE

class ChatApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("Secure E2EE Chat")

        self.store = ChatStore()
        self.users_data = self.store.users
        self.chat_history = self.store.history

        self.client_thread = NetworkClient()
        self.client_thread.signal_login_ok.connect(self.on_login_success)
        self.client_thread.signal_login_fail.connect(self.on_login_fail)
        self.client_thread.signal_new_msg.connect(self.on_new_message)
        self.client_thread.signal_clients_list.connect(self.on_clients_list_received)
        self.client_thread.signal_system_msg.connect(self.on_system_message)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.ask_server_for_clients)

        self.ui.stackedWidget.setCurrentWidget(self.ui.page_login)
        self.ui.textEdit_chat.setReadOnly(True)
        self.ui.action_log_out.setEnabled(False)

        self.ui.action_close_app.triggered.connect(self.close)
        self.ui.action_log_out.triggered.connect(self.perform_logout)

        self.ui.pushButton_new_account.clicked.connect(self.go_to_register)
        self.ui.pushButton_back.clicked.connect(self.go_to_login)
        self.ui.pushButton_login.clicked.connect(self.perform_login)
        self.ui.pushButton_register.clicked.connect(self.perform_register)
        
        self.ui.pushButton_send.clicked.connect(self.send_message_gui)
        self.ui.lineEdit_input.returnPressed.connect(self.send_message_gui)

        self.ui.listWidget_clients_list.itemClicked.connect(self.handle_user_clicked)

    def go_to_register(self):
        self.ui.stackedWidget.setCurrentWidget(self.ui.page_register)

    def go_to_login(self):
        self.ui.stackedWidget.setCurrentWidget(self.ui.page_login)

    def perform_login(self):
        user_id = self.ui.lineEditl_login.text().strip()
        password = self.ui.lineEdit_password.text().strip()
        
        if user_id and password:
            self.ui.pushButton_login.setEnabled(False)
            self.client_thread.authenticate_existing(user_id, password)

    def perform_register(self):
        user_id = self.ui.lineEdit_login_reg.text().strip()
        name = self.ui.lineEdit_name_reg.text().strip()
        password = self.ui.lineEdit_password_reg.text().strip()
        
        if user_id and name and password:
            self.ui.pushButton_register.setEnabled(False)
            self.client_thread.authenticate_new(user_id, name, password)

    def perform_logout(self):
        self.refresh_timer.stop() 
        self.client_thread.close_connection()
        self.client_thread.client_id = None

        self.ui.stackedWidget.setCurrentWidget(self.ui.page_login)
        self.ui.action_log_out.setEnabled(False)
        self.ui.pushButton_login.setEnabled(True)
        self.ui.pushButton_register.setEnabled(True)

        self.ui.lineEdit_password.clear()
        self.ui.textEdit_chat.clear()
        self.ui.label_current_user.setText("User :")
        self.ui.listWidget_clients_list.clear()
        self.users_data.clear()
        self.chat_history.clear()

    def on_login_success(self, client_id):
        self.ui.pushButton_login.setEnabled(True)
        self.ui.pushButton_register.setEnabled(True)
        
        self.ui.stackedWidget.setCurrentWidget(self.ui.page_chat)
        self.ui.action_log_out.setEnabled(True)
        
        self.refresh_timer.start(5000)
        self.ask_server_for_clients()

    def on_login_fail(self, error_msg):
        self.ui.pushButton_login.setEnabled(True)
        self.ui.pushButton_register.setEnabled(True)
        QMessageBox.warning(self, "Login Failed", error_msg)

    def on_clients_list_received(self, cmd_type, raw_list):
        parts = [p.strip() for p in raw_list.split("|") if p.strip()]

        if cmd_type == CMD_ALL:
            for part in parts:
                if "," in part:
                    cid, name = part.split(",", 1)
                    cid = cid.strip()
                    name = name.strip()

                    if cid == self.client_thread.client_id:
                        continue

                    if cid not in self.users_data:
                        self.store.update_user_status(cid, False, name=name, has_unread=False, last_active=time.time() - 1000)
                    else:
                        self.store.update_user_status(cid, self.users_data[cid]["is_online"], name=name)

        elif cmd_type == CMD_ACTIVE:
            for cid in self.users_data:
                self.store.update_user_status(cid, False)

            for part in parts:
                if "," in part:
                    cid, name = part.split(",", 1)
                    cid = cid.strip()
                    name = name.strip()

                    if cid == self.client_thread.client_id:
                        continue

                    if cid not in self.users_data:
                        self.store.update_user_status(cid, True, name=name, has_unread=False, last_active=time.time() - 1000)
                    else:
                        self.store.update_user_status(cid, True, name=name)
                    
        self.refresh_clients_list()

    def on_new_message(self, sender_id, sender_name, msg):
        self.store.add_message(sender_id, "in", sender_name, msg)

        current_item = self.ui.listWidget_clients_list.currentItem()
        current_chat_id = current_item.data(Qt.UserRole) if current_item else None
        
        if sender_id == current_chat_id:
            self.ui.textEdit_chat.append(f"[{sender_name}]: {msg}")
        else:
            if sender_id in self.users_data:
                self.store.update_user_status(sender_id, self.users_data[sender_id]["is_online"], has_unread=True, last_active=time.time())
                self.refresh_clients_list()
            else:
                self.store.update_user_status(sender_id, True, name=sender_name, has_unread=True, last_active=time.time())
                self.refresh_clients_list()

    def on_system_message(self, msg):
        self.ui.textEdit_chat.append(f"<font color='gray'>[SYSTEM]: {msg}</font>")

    def ask_server_for_clients(self):
        self.client_thread.request_clients(CMD_ALL)
        self.client_thread.request_clients(CMD_ACTIVE)

    def send_message_gui(self):
        msg = self.ui.lineEdit_input.text().strip()
        if not msg:
            return
            
        current_item = self.ui.listWidget_clients_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Error", "Please select a user to send the message to.")
            return
            
        target_id = current_item.data(Qt.UserRole)

        self.store.add_message(target_id, "out", "Ja", msg)
        
        self.ui.textEdit_chat.append(f"<font color='blue'>[Ja]: {msg}</font>")
        self.ui.lineEdit_input.clear()
        
        self.client_thread.send_chat_message(target_id, msg)

    def refresh_clients_list(self):
        current_item = self.ui.listWidget_clients_list.currentItem()
        selected_id = current_item.data(Qt.UserRole) if current_item else None

        self.ui.listWidget_clients_list.clear()

        sorted_clients = sorted(
            self.users_data.items(), 
            key=lambda item: item[1]["last_active"], 
            reverse=True
        )

        for client_id, data in sorted_clients:
            status = ""
            if data["has_unread"]:
                status += "🟡 "
            if data["is_online"]:
                status += "🟢 "

            display_text = f"{status}{data['name']} ({client_id})"
            list_item = QListWidgetItem(display_text)
            list_item.setData(Qt.UserRole, client_id)
            self.ui.listWidget_clients_list.addItem(list_item)

            if client_id == selected_id:
                self.ui.listWidget_clients_list.setCurrentItem(list_item)

    def handle_user_clicked(self, item):
        client_id = item.data(Qt.UserRole)
        name = self.users_data[client_id]["name"]
        
        self.ui.label_current_user.setText(f"User : {name} ({client_id})")
        self.ui.textEdit_chat.clear()

        for direction, author, text in self.store.get_messages(client_id):
            if direction == "out":
                self.ui.textEdit_chat.append(f"<font color='blue'>[{author}]: {text}</font>")
            else:
                self.ui.textEdit_chat.append(f"[{author}]: {text}")

        self.store.update_user_status(client_id, self.users_data[client_id]["is_online"], has_unread=False, last_active=time.time())
        self.refresh_clients_list()

        self.client_thread.request_public_key(client_id)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChatApp()
    window.show()
    sys.exit(app.exec())