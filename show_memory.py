# -*- coding: utf-8 -*-

from logging import basicConfig, getLogger, FileHandler, StreamHandler,NullHandler, DEBUG, INFO
fmt = "%(asctime)s %(levelname)s %(name)s :%(message)s"
basicConfig(level=DEBUG, format=fmt)

logger = getLogger("show_memory")
# handler = FileHandler("show_memory"+".log")
# handler = StreamHandler() # StreamHandler()ならば、コンソール出力になる。
handler = NullHandler()
logger.addHandler(handler)
logger.setLevel(INFO)
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
    db.init()
    db.open_session()

    maps = []
    def cb_mapfile(item):
        nonlocal db
        nonlocal maps
        maps.append(item)
        if len(maps) > 3000:
            db.add_maps(maps)
            db.commit()
            maps = []

    mapfile.parse(map_fname, encoding=encoding_detect(map_fname), callback=cb_mapfile)
    db.add_maps(maps)
    db.commit()

    symbols = []
    def callback_symbol(item):
        nonlocal db
        nonlocal symbols
        symbols.append(item)
        if len(symbols) > 3000:
            db.add_symbols(symbols)
            db.commit()
            symbols = []

    crossrefs = []
    def callback_crossref(item):
        nonlocal db
        nonlocal crossrefs
        crossrefs.append(item)
        if len(crossrefs) > 3000:
            db.add_crossrefs(crossrefs)
            db.commit()
            crossrefs = []

    dlafile.parse(dla_fname, encoding=encoding_detect(dla_fname), callback_symbol=callback_symbol, callback_crossref=callback_crossref)
    db.add_symbols(symbols)
    db.add_crossrefs(crossrefs)

    db.close_sessoin()

if __name__ == '__main__':
    create_database("map.map", "dla.txt")


# In [8]: %time show_memory.create_database("DMS_Sub_Appl_1.map", "dmsdla.txt")
# Wall time: 2min 39s