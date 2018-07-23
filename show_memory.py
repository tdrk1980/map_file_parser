# -*- coding: utf-8 -*-

from logging import basicConfig, getLogger, FileHandler, StreamHandler, DEBUG, INFO
fmt = "%(asctime)s %(levelname)s %(name)s :%(message)s"
basicConfig(level=DEBUG, format=fmt)

logger = getLogger("show_memory")
handler = FileHandler("show_memory"+".log") 
# handler = StreamHandler() # StreamHandler()ならば、コンソール出力になる。
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


maps = []
def cb_mapfile(item):
    global maps
    maps.append({"addr":item["addr"], "size":item["size"]})
    if len(maps) > 3000:
        db.add_maps(maps)
        db.commit()
        maps = []


symbols = []
def callback_symbol(item):
    global symbols
    if len(symbols) > 3000:
        db.add_symbols(symbols)
        db.commit()
        symbols = []

crossrefs = []
def callback_crossref(item):
    global crossrefs
    crossrefs.append(item)
    if len(crossrefs) > 3000:
        db.add_crossrefs(crossrefs)
        db.commit()
        crossrefs = []

if __name__ == '__main__':

    logger.debug("start")
    db = database.Database("test.sqlite3", logger=logger)
    db.init()
    db.open_session()

    fname = "map.map"

    mapfile.parse(fname, encoding=encoding_detect(fname), callback=cb_mapfile)
    db.commit()
    logger.debug("end mapfile")


    logger.debug("start dlafile")

    fname = "dmsdla.txt"
    dlafile.parse(fname, encoding=encoding_detect(fname), callback_symbol=callback_symbol, callback_crossref=callback_crossref)
    logger.debug("end dlafile")

    db.close_sessoin()
