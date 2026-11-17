"""Bounded local logs. Never record key events or frame contents."""
from collections import deque
import logging
from logging.handlers import RotatingFileHandler
import os
import threading


class Diagnostics(logging.Handler):
    def __init__(self,directory):
        super().__init__()
        self.entries=deque(maxlen=400)
        self.guard=threading.Lock()
        self.path=directory/'logs'/'smk-webui.log'
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.logger=logging.getLogger('smk-webui.'+str(id(self)))
        self.logger.setLevel(logging.INFO);self.logger.propagate=False
        formatter=logging.Formatter('%(asctime)s %(levelname)s %(message)s',datefmt='%Y-%m-%d %H:%M:%S')
        self.setFormatter(formatter)
        self.file=RotatingFileHandler(self.path,maxBytes=512*1024,backupCount=2,encoding='utf-8')
        self.file.setFormatter(formatter)
        self.logger.addHandler(self);self.logger.addHandler(self.file)
        self.logger.info('Application started; PID %s',os.getpid())

    def emit(self,record):
        with self.guard:self.entries.append(self.format(record))

    def snapshot(self):
        with self.guard:return list(self.entries)

    def finish(self):
        self.logger.info('Application stopped')
        self.logger.removeHandler(self.file);self.file.close()
        self.logger.removeHandler(self);self.close()
