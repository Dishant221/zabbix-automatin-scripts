import json
import os
from cryptography.fernet import Fernet


#APP_SECRET_KEY="REDACTED"

key = os.environ.get("APP_SECRET_KEY")
if not key:
    raise RuntimeError("APP_SECRET_KEY is not set")

f = Fernet(key.encode())

with open("credential_for_prod.json.enc", "rb") as enc_file:
    decrypted_data = f.decrypt(enc_file.read())

config = json.loads(decrypted_data.decode())

# Now use normally
ZABBIX_URL = config["ENV_CRED"]["ZABBIX_URL"]
ZABBIX_TOKEN = config["ENV_CRED"]["ZABBIX_TOKEN"]
DB_USER = config["ENV_CRED"]["DB_CONNECTION"]["user"]
DB_PASSWORD = config["ENV_CRED"]["DB_CONNECTION"]["password"]

print("ZABBIX_URL:", ZABBIX_URL)
print("ZABBIX_TOKEN:"REDACTED"DB_USER:", DB_USER)
print("DB_PASSWORD:", DB_PASSWORD)  
