import json
from cryptography.fernet import Fernet


def decrypt_json_bytes(encrypted_data, fernet):
    decrypted = fernet.decrypt(encrypted_data)
    return json.loads(decrypted.decode())
