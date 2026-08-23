import json
from cryptography.fernet import Fernet


'''
Fernet is a symmetric, authenticated encryption method in Python's cryptography library 
that ensures data cannot be read or modified without a 32-byte base64-encoded secret key.
 It uses AES-128 in CBC mode with SHA256 HMAC for authentication,
   making it secure for sensitive data, tokens, and password storage.
'''

KEY = b"LBxTTNxpFMHVsU8NqXnGIpziDeXV7WVBtqTa4G2ErTw="

file_list =['Creadentail_from_DEV.json','Creadentail_from_PROD.json','Creadentail_from_STAGE.json']

for file in file_list:
    with open(file, "rb") as f:
        data = f.read()

    f = Fernet(KEY)
    encrypted = f.encrypt(data)

    with open("./EncryptedFILES/" + str(file) +".enc", "wb") as f:
        f.write(encrypted)
