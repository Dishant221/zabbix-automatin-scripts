import sys
import json 
import logging
import warnings
import os
import configparser

import Utils.Logger as Logger

class ConfigurationManager(object):
    DBConfig = None
    ZBConfig = None
    SFConfig = None
    SFTPConfig = None
    logger = None

    def __init__(self,_configJson):
        ConfigurationManager.DBConfig = _configJson["ZabbixDatabase"]
        ConfigurationManager.ZBConfig = _configJson["ZabbixServer"]
        ConfigurationManager.SFConfig = _configJson["SalesForce"]
        ConfigurationManager.JIRAConfig = _configJson["JIRAServer"]
        ConfigurationManager.SFTPConfig = _configJson["SFTPServer"]
        ConfigurationManager.logger = logging.getLogger(Logger.eventID)

    def GetSFQueue(solutionName):
        queueDetails = None
                
        try:
            for queue  in ConfigurationManager.SFConfig["queues"]:
                if queue["solution"].upper() == solutionName.upper():
                    queueDetails = queue
                    break

            if queueDetails is None:
                for queue  in ConfigurationManager.SFConfig["queues"]:
                    if queue["solution"].upper() == "Default".upper():
                        queueDetails = queue
                        break

            ConfigurationManager.logger.debug(queueDetails)

        except Exception as e:
            ConfigurationManager.logger.error(e)

        return queueDetails
