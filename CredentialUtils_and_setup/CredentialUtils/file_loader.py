import os


def load_encrypted_file(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Encrypted file not found: {file_path}")
    with open(file_path, "rb") as f:
        return f.read()
    