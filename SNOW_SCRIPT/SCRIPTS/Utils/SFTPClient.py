import paramiko
if not hasattr(paramiko, 'DSSKey'):
    paramiko.DSSKey = paramiko.RSAKey

import pysftp
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

#Ref: https://pysftp.readthedocs.io/en/release_0.2.9/cookbook.html#pysftp-connection

class SFTPClient(object):
    def __init__(self,sftpConfig):
        try:
            self.logger = logging.getLogger(Logger.eventID)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                cnopts = pysftp.CnOpts(knownhosts=None)
            cnopts.hostkeys = None    
            self.ClientHandle =pysftp.Connection(host=sftpConfig["host"],username=sftpConfig["user"],private_key=sftpConfig["keyfile"],private_key_pass=sftpConfig["keyPhrase"],cnopts=cnopts)
        except Exception as e:
            self.logger.error(e)
            raise e;

    def Put(self,source,destination):
        fileAttributes = None
        try:
            fileAttributes = self.ClientHandle.put(source,destination)
        except Exception as e:
            self.logger.error(e)

        return fileAttributes

    def Get(self,source,destination):
        bSuccess = False
        try:
            fileAttributes = self.ClientHandle.get_d(source,destination)
            bSuccess=True
        except Exception as e:
            self.logger.error(e)

        return bSuccess

    def List(self, remotePath):
        try:
            return self.ClientHandle.listdir(remotePath)
        except Exception as e:
            self.logger.error(e)
            raise e

    def Download(self, source, destination):
        try:
            self.ClientHandle.get(source, destination)
        except Exception as e:
            self.logger.error(e)
            raise e