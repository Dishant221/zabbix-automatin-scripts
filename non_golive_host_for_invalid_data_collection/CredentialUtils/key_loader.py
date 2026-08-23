import os
from cryptography.fernet import Fernet


def load_fernet_from_env(env_key_name="ZABBIX_SCRIPTS_APP_SECRET_KEY"):
    key = os.environ.get(env_key_name)
    if not key:
        raise RuntimeError(f"{env_key_name} is not set")
    return Fernet(key.encode())
