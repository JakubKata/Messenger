import os

import rsa


class CryptoManager:
    def __init__(self, client_id):
        self.client_id = client_id
        self.private_key, self.public_key = self._load_or_generate_keys()

    def _private_key_path(self):
        return f"private_{self.client_id}.pem"

    def _public_key_path(self):
        return f"public_{self.client_id}.pem"

    def _load_or_generate_keys(self):
        private_file = self._private_key_path()
        public_file = self._public_key_path()

        if os.path.exists(private_file) and os.path.exists(public_file):
            with open(private_file, "rb") as file:
                private_key = rsa.PrivateKey.load_pkcs1(file.read())
            with open(public_file, "rb") as file:
                public_key = rsa.PublicKey.load_pkcs1(file.read())
            return private_key, public_key

        public_key, private_key = rsa.newkeys(1024)
        with open(private_file, "wb") as file:
            file.write(private_key.save_pkcs1())
        with open(public_file, "wb") as file:
            file.write(public_key.save_pkcs1())
        return private_key, public_key

    def encrypt(self, message: str, receiver_pub_key: rsa.PublicKey) -> str:
        return rsa.encrypt(message.encode(), receiver_pub_key).hex()

    def decrypt(self, encrypted_hex: str) -> str:
        encrypted_bytes = bytes.fromhex(encrypted_hex)
        return rsa.decrypt(encrypted_bytes, self.private_key).decode()