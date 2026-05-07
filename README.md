# Project Messenger

Project Messenger is a small, secure client–server messenger written in Python. It uses TLS for transport security and RSA for end-to-end message encryption between clients. The repository contains a server and a client application with a lightweight GUI.

Supported scenarios:

- User registration and login
- Active / full clients lists
- Sending encrypted messages between clients
- Offline message storage and delivery when the recipient reconnects
- Server verification using a shared secret key (configured via `SECRET_KEY`)

---

## Features

- TLS-encrypted TCP connections (via Python `ssl`)
- Asymmetric message encryption with `rsa`
- New-client registration and existing-client login flows
- Offline message storage using SQLite
- Simple client GUI using `PySide6`
- Public-key exchange and storage in the server database

---

## Requirements

- Python 3.8 or newer
- A virtual environment (recommended)
- Required Python packages: `PySide6`, `rsa`, `python-dotenv` (see `requirements.txt`)
- OpenSSL (optional — used by `generate_cert.py` to create self-signed certificates)

The project is licensed under the MIT License (see `LICENSE`).

---

## Quick Start (Windows / Linux)

1. Create and activate a virtual environment:

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Generate a server TLS certificate (either with OpenSSL or the helper script):

```bash
# using OpenSSL
openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt -days 365 -nodes

# or run the helper (requires OpenSSL on PATH)
python server/generate_cert.py
```

4. Create a `.env` file in the repository root with the following example values:

```text
SERVER_IP=127.0.0.1
SERVER_PORT=12345
SECRET_KEY=changeme
```

5. (Optional) Edit `server/config.json` to adjust `MAX_CLIENTS` or other server settings.

---

## Run

Start the server:

```bash
python server/server.py
```

Start the client GUI:

```bash
python client/app.py
```

---

## Notes

- The server uses `server.crt` / `server.key` (generated above). The client expects `server.crt` to validate the server certificate.
- A `requirements.txt` file is included with the main dependencies. Pin package versions there if you need reproducible installs.
- The server reads `server/config.json` at startup; keep it when packaging or deploying.

---

## Project Structure

```text
Project_messenger/
├── LICENSE
├── README.md
├── requirements.txt
├── client/
│   ├── app.py
│   ├── chat_store.py
│   ├── crypto_manager.py
│   ├── network.py
│   ├── protocol.py
│   ├── ui_chat.py
│   └── chat_gui.ui
├── server/
│   ├── config.json
│   ├── database.py
│   ├── generate_cert.py
│   ├── protocol.py
│   └── server.py
└── .env (not committed)
```

---

## License

MIT

