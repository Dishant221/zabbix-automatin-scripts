from CredentialUtils.key_loader import load_fernet_from_env
from CredentialUtils.file_loader import load_encrypted_file
from CredentialUtils.json_decryptor import decrypt_json_bytes


class ZBCredentials:
    def __init__(self, enc_file_path: str, env_key_name: str = "APP_SECRET_KEY"):
        self.enc_file_path = enc_file_path
        self.env_key_name = env_key_name

    def load(self) -> dict:
        fernet = load_fernet_from_env(self.env_key_name)
        encrypted_data = load_encrypted_file(self.enc_file_path)
        return decrypt_json_bytes(encrypted_data, fernet)
