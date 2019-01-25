# -*- coding: utf-8 -*-

from logging import getLogger, DEBUG, NullHandler, StreamHandler, FileHandler
selflogger = getLogger(__name__)
selflogger.setLevel(DEBUG)
selflogger.addHandler(NullHandler()) # 必要に応じてStremaHandlerなどを設定する
selflogger.propagate = False

# https://qiita.com/msrks/items/15144746ff4f7aced4b5

from sqlalchemy import create_engine 
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class Map(Base):
    __tablename__ = 'db_map'

    id = Column(Integer, primary_key=True)
    addr = Column(Integer)
    size = Column(Integer)
    sect = Column(String)
    sym = Column(String)
    def __repr__(self):
        return "<Map(id={0}, addr={1}, size={2}, sect={3}, sym={4})>".format(self.id, self.addr, self.size, self.sect, self.sym)


class Symbol(Base):
    __tablename__ = 'db_symbol'

    id = Column(Integer, primary_key=True)
    file = Column(String)
    isym = Column(Integer)
    name = Column(String)
    addr = Column(Integer)
    scope = Column(String)
    sect = Column(String)

    def __repr__(self):
        return "<Symbol(file={0},isym={1}, name={2}, addr={3}, scope={4}, sect={5})>".format(self.file, self.isym, self.name, self.addr, self.scope, self.sect)

class Crossref(Base):
    __tablename__ = 'db_crossref'

    id = Column(Integer, primary_key=True)
    file = Column(String)
    isym = Column(Integer)
    reftype = Column(String)
    ifile = Column(Integer)
    line = Column(Integer)
    col = Column(Integer)

    def __repr__(self):
        return "<Crossref(file={0}, isym={1}, reftype={2}, ifile={3}, line={4}, col={5})>".format(self.file, self.isym, self.reftype, self.ifile, self.line, self.col)

class Database:
    def __init__(self, db_fname, echo=False, logger=None):
        self.db_fname = db_fname
        self.engine = None
        self.session = None
        self.log = logger or selflogger

        self.maps = []
        self.MAPS_COMMIT_LEN = 10000

        self.symbols = []
        self.SYMBOLS_COMMIT_LEN = 10000

        self.crossrefs = []
        self.CROSSREF_COMMIT_LEN = 20000


        self.init(echo=echo)


    def init(self,echo=False):
        self.engine = create_engine("sqlite:///{}".format(self.db_fname), echo=echo)

        # 既存テーブルのドロップ
        self.engine.execute(f"DROP TABLE IF EXISTS {Map.__tablename__}")
        self.engine.execute(f"DROP TABLE IF EXISTS {Symbol.__tablename__}")
        self.engine.execute(f"DROP TABLE IF EXISTS {Crossref.__tablename__}")

        # テーブル作成
        Base.metadata.create_all(self.engine)

        # View作成
        self.engine.execute(f"DROP VIEW  IF EXISTS Syms")
        self.engine.execute(self.sql_syms_view)

        self.engine.execute(f"DROP VIEW  IF EXISTS bss")
        self.engine.execute(self.sql_bss_view)

        self.engine.execute(f"DROP VIEW  IF EXISTS data")
        self.engine.execute(self.sql_data_view)

        self.engine.execute(f"DROP VIEW  IF EXISTS rodata")
        self.engine.execute(self.sql_rodata_view)


    def open(self):
        if self.engine:
            if self.session :
                self.maps = []
                self.symbols = []
                self.crossrefs = []
                self.log.debug("ignored. session already opened.")
            else:
                self.session = sessionmaker(bind=self.engine)()
                self.log.info("session opened.")
        else:
            self.log.warn("engine not found.")
    
    def close(self):
        if self.session:

            self.commit_all()
            self.maps=[]
            self.symbols=[]
            self.crossrefs=[]

            self.session.close()
            self.session = None

            self.log.info("session closed.")
        else:
            self.log.debug("ignored. already closed")
    

    def cb_map(self, item):
        self.maps.append(item)
        if len(self.maps) > self.MAPS_COMMIT_LEN:
            self.commit_maps()
            self.maps = []

    def cb_symbol(self, item):
        self.symbols.append(item)
        if len(self.symbols) > self.SYMBOLS_COMMIT_LEN:
            self.commit_symbols()
            self.symbols = []

    def cb_crossref(self, item):
        self.crossrefs.append(item)
        if len(self.crossrefs) > self.CROSSREF_COMMIT_LEN:
            self.commit_crossrefs()
            self.crossrefs = []
 
    def commit_maps(self):
        if self.session:
            self.session.add_all([Map(**s) for s in self.maps])
            self.session.flush()
            self.session.commit()
            self.log.info("session committed (maps)")
        else:
            self.log.debug("ignoted. already closed")
   
    def commit_symbols(self):
        if self.session:
            self.session.add_all([Symbol(**s) for s in self.symbols])
            self.session.flush()
            self.session.commit()
            self.log.info("session committed (symbols)")
        else:
            self.log.debug("ignoted. already closed")

    def commit_crossrefs(self):
        if self.session:
            self.session.add_all([Crossref(**s) for s in self.crossrefs])
            self.session.flush()
            self.session.commit()
            self.log.info("session committed (crossrefs)")
        else:
            self.log.debug("ignoted. already closed")


    def commit_all(self):
        if self.session:
            self.commit_maps()
            self.commit_symbols()
            self.commit_crossrefs()
            self.log.info("session committed")
        else:
            self.log.debug("ignoted. already closed")
    
    @property
    def sql_syms_view(self):
        sql = f"""
        CREATE VIEW Syms
        AS
        SELECT s.file, s.name, s.addr, m.size, s.scope, s.sect, c.reftype
        FROM {Symbol.__tablename__} s
        INNER JOIN {Crossref.__tablename__} c ON (s.file = c.file) AND (s.isym = c.isym)
        INNER JOIN {Map.__tablename__} m ON s.addr = m.addr
        """
        return sql

    @property  
    def sql_bss_view(self):
        sql = f"""
        CREATE VIEW bss
        AS
        SELECT DISTINCT file, name, size
        FROM Syms
        WHERE sect = "Bss" AND (reftype = "Definition" OR reftype = "Declaration")
        """
        return sql

    @property  
    def sql_data_view(self):
        sql = f"""
        CREATE VIEW data
        AS
        SELECT DISTINCT file, name, size
        FROM Syms
        WHERE sect = "Data" AND reftype = "Definition"
        """
        return sql

    @property  
    def sql_rodata_view(self):
        sql = """
        CREATE VIEW rodata
        AS
        SELECT DISTINCT file, name, size
        FROM Syms
        WHERE sect = "Data-In-Text" AND reftype = "Definition"
        ORDER BY file DESC
        """
        return sql


if __name__ == '__main__':
    # # 引数の解析
    # from argparse import ArgumentParser
    # parser = ArgumentParser()
    # parser.add_argument("file", help="解析するマップファイル",  type=str, nargs=1)
    # args = parser.parse_args()

    # デバッグログ出力の設定
    from logging import getLogger, DEBUG, StreamHandler
    logger = getLogger("test")
    logger.addHandler(StreamHandler())
    logger.setLevel(DEBUG)
    logger.propagate = False
    
    # db = Database("test.sqlite3")
    
    # db.init(echo=True)
    # db.add_maps([{"addr":12345, "size":11}])
    # db.add_maps([{"addr":45678, "size":12123}])
    # db.add_symbols([{"file":"aaaa.c", "isym":12334, "name":"system_manager_get", "addr":12334, "scope":"extern", "sect":".bss"}])
    # db.add_crossrefs([{"file":"aaaa.c", "isym":12334, "reftype":"definition", "ifile":1, "line":1111, "col":2222}])
    # db.commit()
