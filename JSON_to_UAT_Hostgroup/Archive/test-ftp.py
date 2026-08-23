import sys
import json 
import jsonquery
import logging
import warnings
import os
import configparser
import time
from logging.handlers import RotatingFileHandler
from Utils import *



appBaseDirectory = os.path.dirname(os.path.realpath(__file__))
logfilePATH=os.path.join(appBaseDirectory,"DATA","LOG_OUTPUT","json_to_uat.log")


logging.basicConfig(filename=logfilePATH,
                    filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
config = None

#elif envType.upper() == "Production".upper(): 
with open(appBaseDirectory + "/Data/IN/" + "JIRA_ZB_INT_CONFIG_PROD.json") as f:
    config = json.load(f) 

configManager = ConfigurationManager(config)

sftpConfig = configManager.SFTPConfig


try:
    
    _sftpClient =  SFTPClient(sftpConfig)

    for f in _sftpClient.List("/CI_SFTP/ci-sftp/inbound/Zabbix/Custom Json"):
        logging.info(f"Processing file: {f}")
        _sftpClient.Download("/CI_SFTP/ci-sftp/inbound/Zabbix/Custom Json/" + f, appBaseDirectory + "/Data/IN/" + f)
    
except Exception as e:
    logging.error(e)
    raise(e)