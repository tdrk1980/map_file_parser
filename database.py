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

    def __repr__(self):
        return "<Map(id={0}, addr={1}, size={2})>".format(self.id, self.addr, self.size)


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
    def __init__(self, db_fname, logger=None):
        self.db_fname = db_fname
        self.engine = None
        self.session = None
        self.log = logger or selflogger

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


    def open_session(self):
        if self.engine:
            if self.session :
                self.log.debug("ignoted. session already opened.")
            else:
                self.session = sessionmaker(bind=self.engine)()
                self.log.info("session opened.")
        else:
            self.log.warn("engine not found.")
    
    def close_sessoin(self):
        if self.session:
            self.session.commit()
            self.session = None
            self.log.info("session alreadyclosed.")
        else:
            self.log.debug("ignored. already closed")
    
    def add_maps(self, maps=[]):
        self.add_items(Map, maps)

    def add_symbols(self, symbols=[]):
        self.add_items(Symbol, symbols)

    def add_crossrefs(self, crossrefs=[]):
        self.add_items(Crossref, crossrefs)
    
    def add_items(self, class_, items=[]):
        self.open_session()
        if self.session:
            items = [class_(**s) for s in items]
            self.session.add_all(items)
            self.log.info(items)
        else:
            self.log.warn("session not opened.")
    
    def commit(self):
        if self.session:
            self.session.commit()
            self.log.info("session committed")
        else:
            self.log.debug("ignoted. already closed")
    
    @property
    def sql_syms_view(self):
        sql = f"""
        CREATE VIEW Syms
        AS
        SELECT s.file, s.isym, s.name, s.addr, m.size, s.scope, s.sect, c.line, c.col
        FROM {Symbol.__tablename__} INNER JOIN {Map.__tablename__} m ON s.addr = m.addr
        INNER JOIN {Crossref.__tablename__} c ON (s.file = c.file) AND (s.isym = c.isym)
        """
        return sql

    @property  
    def sql_bss_view(self):
        sql = f"""
        CREATE VIEW bss
        AS
        SELECT file, sect AS section, SUM(size) AS total_bss_size
        FROM Syms
        WHERE sect = "Bss"
        GROUP BY file, sect
        ORDER BY SUM(size) DESC
        """
        return sql

    @property  
    def sql_data_view(self):
        sql = f"""
        CREATE VIEW data
        AS
        SELECT file, sect AS section, SUM(size) AS total_bss_size
        FROM Syms
        WHERE sect = "Data"
        GROUP BY file, sect
        ORDER BY SUM(size) DESC
        """
        return sql

    @property  
    def sql_rodata_view(self):
        sql = """
        CREATE VIEW rodata
        AS
        SELECT file, sect AS section, SUM(size) AS total_rodata_size
        FROM Syms
        WHERE sect = "Data-In-Text"
        GROUP BY file, sect
        ORDER BY SUM(size) DESC
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
    
    db = Database("test.sqlite3")
    
    db.init(echo=True)
    db.add_maps([{"addr":12345, "size":11}])
    db.add_maps([{"addr":45678, "size":12123}])
    db.add_symbols([{"file":"aaaa.c", "isym":12334, "name":"system_manager_get", "addr":12334, "scope":"extern", "sect":".bss"}])
    db.add_crossrefs([{"file":"aaaa.c", "isym":12334, "reftype":"definition", "ifile":1, "line":1111, "col":2222}])
    db.commit()
