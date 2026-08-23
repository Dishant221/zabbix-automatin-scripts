from CredentialUtils import ZBCredentials

creds = ZBCredentials(
    enc_file_path="../encrypted/credential_for_prod.json.enc"
)

config = creds.load()

ZABBIX_URL = config["ENV_CRED"]["ZABBIX_URL"]
ZABBIX_TOKEN = config["ENV_CRED"]["ZABBIX_TOKEN"]

print(ZABBIX_URL)