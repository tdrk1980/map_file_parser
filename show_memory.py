# -*- coding: utf-8 -*-

from logging import basicConfig, getLogger, FileHandler, StreamHandler,NullHandler, DEBUG, INFO
logger = getLogger(__name__)
logger.addHandler(NullHandler())
logger.setLevel(DEBUG)
logger.propagate = False

import re
import mapfile
import dlafile
import database
from chardet.universaldetector import UniversalDetector

def encoding_detect(fname):
    detector = UniversalDetector()
    with open(fname, "rb") as f:
        for binary in f:
            detector.feed(binary)
            if detector.done:
                break
    detector.close()
    return detector.result["encoding"]


def create_database(map_fname, dla_fname, db_name="test.sqlite3"):
    db = database.Database(db_name)
    db.open()

    mapfile.parse(map_fname, encoding=encoding_detect(map_fname), callback=db.cb_map)
    dlafile.parse(dla_fname, encoding=encoding_detect(dla_fname), callback_symbol=db.cb_symbol, callback_crossref=db.cb_crossref)
    
    db.close()

if __name__ == '__main__':
    import pandas as pd
    import time
    start = time.time()

    create_database("map.map", "dla.txt")

    elapsed_time = time.time() - start
    print ("elapsed_time:{0}".format(elapsed_time) + "[sec]")
    
    
    
# In [8]: %time show_memory.create_database("DMS_Sub_Appl_1.map", "dmsdla.txt")
# Wall time: 2min 39s
# elapsed_time:166.09351086616516[sec]


# (base) D:\user\zf75944\python\map_file_parser>python show_memory.py
# elapsed_time:295.36812257766724[sec]
# self.maps = []
# self.MAPS_COMMIT_LEN = 10000
# self.symbols = []
# self.SYMBOLS_COMMIT_LEN = 10000
# self.crossrefs = []
# self.CROSSREF_COMMIT_LEN = 20000
# ↑メモリが定常的に50 MB


# (base) D:\user\zf75944\python\map_file_parser>python show_memory.py
# elapsed_time:357.6771683692932[sec]
# self.maps = []
# self.MAPS_COMMIT_LEN = 3000
# self.symbols = []
# self.SYMBOLS_COMMIT_LEN = 3000
# self.crossrefs = []
# self.CROSSREF_COMMIT_LEN = 10000
# メモリは34MB

# (base) D:\user\zf75944\python\map_file_parser>python show_memory.py
# elapsed_time:307.20891785621643[sec]
# self.maps = []
# self.MAPS_COMMIT_LEN = 3000
# self.symbols = []
# self.SYMBOLS_COMMIT_LEN = 3000
# self.crossrefs = []
# self.CROSSREF_COMMIT_LEN = 20000
# 27～49MB

# (base) D:\user\zf75944\python\map_file_parser>python show_memory.py
# elapsed_time:305.3802263736725[sec]
# self.maps = []
# self.MAPS_COMMIT_LEN = 3000
# self.symbols = []
# self.SYMBOLS_COMMIT_LEN = 3000
# self.crossrefs = []
# self.CROSSREF_COMMIT_LEN = 30000
# 32～70MB