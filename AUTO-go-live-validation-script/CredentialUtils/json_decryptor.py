import json
from cryptography.fernet import Fernet


def decrypt_json_bytes(encrypted_data, fernet):
    decrypted = fernet.decrypt(encrypted_data)
    print("Decryption successful.")
    #print(f"Decrypted data (bytes): {decrypted}")
    return json.loads(decrypted.decode())
