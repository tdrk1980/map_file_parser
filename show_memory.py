# -*- coding: utf-8 -*-

# https://qiita.com/amedama/items/b856b2f30c2f38665701#%E6%9B%B4%E6%96%B0-2017-07-06-2017-07-07
from logging import basicConfig, getLogger, FileHandler, DEBUG

# これはメインのファイルにのみ書く
basicConfig(level=DEBUG)

# これはすべてのファイルに書く
logger = getLogger(__name__)

# https://qiita.com/amedama/items/b856b2f30c2f38665701#%E9%95%B7%E3%81%8F%E3%81%AA%E3%81%A3%E3%81%9F
handler = FileHandler(__name__+".log")
logger.addHandler(handler)
logger.propagate = False

import re
import mapfile

if __name__ == '__main__':
    def mapitem(i):
        pass
        logger.debug(i)
    mapfile.parse("map.map", mapitem)

