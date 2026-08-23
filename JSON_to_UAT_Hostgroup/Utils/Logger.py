import os
import sys

import os.path
from os import path

import logging
import logging.handlers

class Logger(object):
    eventID=''
    appBaseDirectory=''
    moduleName=''


    #CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET

    def __init__(self,_eventID,moduleFile):
        try:
            Logger.eventID = _eventID
            Logger.appBaseDirectory=os.path.dirname(os.path.realpath(moduleFile))
            if sys.platform.upper() == 'WIN32':
                tmpFilePathArray = (os.path.splitext(os.path.realpath(moduleFile))[0]).split("\\")
            elif sys.platform.upper() =='LINUX':
                 tmpFilePathArray = (os.path.splitext(os.path.realpath(moduleFile))[0]).split("/")

            Logger.moduleName = tmpFilePathArray[tmpFilePathArray.__len__()-1]

            if path.exists(Logger.appBaseDirectory+"/Log") == False:
                os.mkdir(Logger.appBaseDirectory+"/Log")

            logFileName = Logger.appBaseDirectory+"/Log/"+Logger.moduleName+".log"
            lofFileSize = 10 * 1024 * 1024 #10MB
                        
            rotatingFileHandler = logging.handlers.RotatingFileHandler(logFileName, maxBytes=lofFileSize, backupCount=50)
            streamHandler = logging.StreamHandler(sys.stdout) 
            
            logFormatter = logging.Formatter('{asctime} {name} {levelname:8s} {module:25s} {lineno:d} {message}',style='{')            
            
            rotatingFileHandler.setFormatter(logFormatter)
            streamHandler.setFormatter(logFormatter)

            logger = logging.getLogger(_eventID)
            logger.addHandler(rotatingFileHandler)
            logger.addHandler(streamHandler)

            logger.setLevel(logging.DEBUG)

        except Exception as e:
            print(e)