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


if __name__ == '__main__':

    logger.debug("start")
    db = database.Database("test.sqlite3")
    db.init()
    db.open_session()

    maps = []
    def cb_mapfile(item):
        global db
        global maps
        maps.append(item)
        if len(maps) > 3000:
            db.add_maps(maps)
            db.commit()
            maps = []

    symbols = []
    def callback_symbol(item):
        global db
        global symbols
        symbols.append(item)
        if len(symbols) > 3000:
            db.add_symbols(symbols)
            db.commit()
            symbols = []

    crossrefs = []
    def callback_crossref(item):
        global db
        global crossrefs
        crossrefs.append(item)
        if len(crossrefs) > 3000:
            db.add_crossrefs(crossrefs)
            db.commit()
            crossrefs = []

    fname = "map.map"

    mapfile.parse(fname, encoding=encoding_detect(fname), callback=cb_mapfile)
    db.add_maps(maps)
    db.commit()

    fname = "dmsdla.txt"
    dlafile.parse(fname, encoding=encoding_detect(fname), callback_symbol=callback_symbol, callback_crossref=callback_crossref)
    db.add_symbols(symbols)
    db.add_crossrefs(crossrefs)

    db.close_sessoin()
