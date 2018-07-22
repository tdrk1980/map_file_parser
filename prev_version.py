# -*- coding: utf-8 -*-

# https://qiita.com/amedama/items/b856b2f30c2f38665701#%E6%9B%B4%E6%96%B0-2017-07-06-2017-07-07
from logging import basicConfig, getLogger, DEBUG

# これはメインのファイルにのみ書く
basicConfig(level=DEBUG)

# これはすべてのファイルに書く
logger = getLogger(__name__)

logger.debug('hello')

import re
import pathlib
from sqlalchemy import create_engine 
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey
from sqlalchemy.orm import sessionmaker
import pandas as pd

Base = declarative_base()

class Map(Base):
    __tablename__ = 'mapdb'

    id = Column(Integer, primary_key=True)
    addr = Column(Integer)
    size = Column(Integer)

    def __repr__(self):
        return "<Map(id={0}, addr={1}, size={2})>".format(self.id, self.addr, self.size)


class Sym(Base):
    __tablename__ = 'symdb'

    id = Column(Integer, primary_key=True)
    file = Column(String)
    isym = Column(Integer)
    name = Column(String)
    addr = Column(Integer)
    scope = Column(String)
    sect = Column(String)

    def __repr__(self):
        return "<Symbol(file={0},isym={1}, name={2}, addr={3}, scope={4}, sect={5})>".format(self.file, self.isym, self.name, self.addr, self.scope, self.sect)

class Cref(Base):
    __tablename__ = 'crefdb'

    id = Column(Integer, primary_key=True)
    file = Column(String)
    isym = Column(Integer)
    reftype = Column(String)
    ifile = Column(Integer)
    line = Column(Integer)
    col = Column(Integer)

    def __repr__(self):
        return "<Cref(file={0}, isym={1}, reftype={2}, ifile={3}, line={4}, col={5})>".format(self.file, self.isym, self.reftype, self.ifile, self.line, self.col)



re_event = re.compile(
    "^Actual Calls$|^Auxs$|^Cross References$|^Files$|^Frames$" +
    "|^Global Symbols$|^Hash Define Hashs$|^Hash Defines$|^Header$" +
    "|^Include References$|^Procs$|^Static Calls$|^Symbols$|^Typedefs$"
)


def get_event(s):
    m = re_event.search(s)
    ev = {"event": None, "param": None}
    if m:
        ev["event"] = m.group()
    else:
        ev["event"] = "content"
        ev["param"] = s
    return ev


re_src_name = re.compile(
    "^(0:) *\"(.+?)\" lc:C.*"
)


def get_src_name(s):
    m = re_src_name.search(s.strip())
    if m:
        return pathlib.Path(m.group(2)).name
    else:
        return None


re_symbol = re.compile(
    "^(?P<isym>\d+?): *\"(?P<name>.+?)\" *(?P<addr>0x[0-9A-Fa-f]{8}), (?P<scope>.+?)  (?P<sect>.+?) "
)


def get_symbol(s):
    m = re_symbol.search(s)
    if m:
        return {"name": m.group("name"), "isym": m.group("isym"), "addr": m.group("addr"), "scope": m.group("scope"), "sect": m.group("sect")}
    else:
        return None

# ↓のようなフォーマットに合う正規表現
# 9873:iSym:1552 reftype:Definition file:0 line:779 col:2 
re_isym_reftype = re.compile(
    "^\d+?: *iSym:(?P<isym>\d+?) *reftype:(?P<reftype>.+?) file:(?P<file>\d+?) line:(?P<line>\d+?) col:(?P<col>\d+?)"
)


def get_isym_reftype(s):
    m = re_isym_reftype.search(s)
    if m:
        return {"isym": m.group("isym"), "reftype": m.group("reftype"), "file": m.group("file"), "line": m.group("line"), "col": m.group("col")}
    else:
        return None




def mapfile(map_fname, cb_map=None):
    re_map = re.compile("\..+? +(?P<addr>[0-9A-Fa-f]{8})\+(?P<size>[0-9A-Fa-f]{6}) _.*")
    with open(map_fname) as f:
        for s in f:
            s = s.strip()
            m = re_map.search(s)
            if m:
                size = int(m.group("size"),16)
                if size > 0:
                    addr = "0x" + m.group("addr")
                    if cb_map:
                        cb_map({"addr": addr, "size":size})


def dlafile(dla_fname, cb_map=None, cb_sym=None, cb_cref=None):
    src_name = None
    with open(dla_fname, "r") as f:
        cur_state = nxt_state = "init"
        
        for i, s in enumerate(f, 1):
            cur_state = nxt_state
            ev = get_event(s)

            if cur_state == "init":
                if ev["event"] in ["Files"]:
                    src_name = None
                    nxt_state = "parseFiles"
                else:
                    pass

            elif cur_state == "parseFiles":
                if ev["event"] in ["content"]:
                    src_name = get_src_name(ev["param"])
                    if src_name:
                        # contents includes source file name
                        nxt_state = "joinSymbolsCrossRef"
                    else:
                        pass
                else:
                    nxt_state = "init"

            elif cur_state in ["joinSymbolsCrossRef"]:
                if ev["event"] in ["Symbols", "Global Symbols"]:
                    nxt_state = "parseSymbols"
                elif ev["event"] in ["Cross References"]:
                    nxt_state = "parseCrossReferences"
                elif ev["event"] in ["Header"]:
                    nxt_state = "init"
                else:
                    pass

            elif cur_state in ["parseSymbols"]:
                if ev["event"] in ["content"]:
                    sym = get_symbol(ev["param"])
                    if sym:
                        symdic = {"file":src_name, "name":sym["name"], "addr": sym["addr"], "isym":sym["isym"], "scope": sym["scope"], "sect": sym["sect"]}
                        if cb_sym:
                            cb_sym(symdic)
                    else:
                        pass
                elif ev["event"] in ["Symbols", "Global Symbols"]:
                    pass
                elif ev["event"] in ["Header"]:
                    nxt_state = "init"
                else:
                    nxt_state = "joinSymbolsCrossRef"

            elif cur_state in ["parseCrossReferences"]:
                if ev["event"] in ["content"]:
                    cr = get_isym_reftype(ev["param"])
                    if cr:
                        crdic = {"file":src_name, "isym": cr["isym"], "reftype": cr["reftype"], "ifile": cr["file"], "line": cr["line"], "col": cr["col"]}
                        if cb_cref:
                            cb_cref(crdic)
                else:
                    nxt_state = "init"

def create_table(dla_fname, map_fname, db_fname):
    engine = create_engine("sqlite:///{}".format(db_fname), echo=False)
    engine.execute("DROP TABLE IF EXISTS {}".format("mapdb"))
    engine.execute("DROP TABLE IF EXISTS {}".format("symdb"))
    engine.execute("DROP TABLE IF EXISTS {}".format("crefdb"))
    engine.execute("DROP VIEW  IF EXISTS {}".format("Syms"))

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    maps = []
    def cb_map(i):
        item = Map(**i)
        nonlocal maps
        maps.append(item)
        if len(maps) > 3000:
            nonlocal session
            print(item)
            session.add_all(maps)
            maps = []
 
    print("---start mapfile---")
    mapfile(map_fname, cb_map)
    session.add_all(maps)

    syms = []
    def cb_sym(i):
        if "Bss" in i["sect"]:
            i["sect"] = ".bss"
        elif "Data-In-Text" in i["sect"]:
            i["sect"] = ".rodata"
        else:
            # 76:  "IOR_GRECCCTL_GRAMC" 0xffc64000, Extern  Absolute volatile C ULong 
            # のような直接的にアドレス割付されるもの(Absolute volatile)は無視しておく
            return None
  
        item = Sym(**i)
        nonlocal syms
        syms.append(item)
        if len(syms) > 1000:
            nonlocal session
            print(item)
            session.add_all(syms)
            syms = []

    cref = []
    def cb_cref(i):
        if i["reftype"] == "Definition" and i["ifile"] == "0":
            item = Cref(**i)
            nonlocal cref
            cref.append(item)
            if len(cref) > 10000:
                nonlocal session
                print(item)
                session.add_all(cref)
                cref = []

    print("---start dlafile---")
    dlafile(dla_fname, cb_map, cb_sym, cb_cref)
    session.add_all(syms)
    session.add_all(cref)

    print("---start commit all items---")
    session.commit()

    session.execute(
    """
    CREATE VIEW Syms
    AS
    SELECT s.file, s.isym, s.name, s.addr, m.size, s.scope, s.sect, c.line, c.col
    FROM symdb s INNER JOIN mapdb m ON s.addr = m.addr
    INNER JOIN crefdb c ON (s.file = c.file) AND (s.isym = c.isym)
    """)

    session.execute(
    """
    CREATE VIEW bss
    AS
    SELECT file, sect AS section, SUM(size) AS total_bss_size
    FROM Syms
    WHERE sect = ".bss"
    GROUP BY file, sect
    ORDER BY SUM(size) DESC
    """
    )

    session.execute(
    """
    CREATE VIEW rodata
    AS
    SELECT file, sect AS section, SUM(size) AS total_rodata_size
    FROM Syms
    WHERE sect = ".rodata"
    GROUP BY file, sect
    ORDER BY SUM(size) DESC
    """
    )

    session.commit()

    print("---end---")
    

def _testdb():
    create_table("gdump_app.txt","map.map", "testdb.sqlite3")
    engine = create_engine("sqlite:///{}".format("testdb.sqlite3"), echo=True)
    session = sessionmaker(bind=engine)()
    
    sql = """SELECT file, sect AS section, SUM(size) AS total_size FROM Syms WHERE sect = ".bss" GROUP BY file, sect ORDER BY SUM(size) DESC"""
    df = pd.read_sql_query(sql=sql, con=engine)
    df.head(10).plot.bar(x="file", y="total_size")

    sql = """SELECT file, sect AS section, SUM(size) AS total_size FROM Syms WHERE sect = ".rodata" GROUP BY file, sect ORDER BY SUM(size) DESC"""
    df = pd.read_sql_query(sql=sql, con=engine)
    df.head(10).plot.bar(x="file", y="total_size")


if __name__ == '__main__':
     create_table("gdump_app.txt","map.map", "test.sqlite3")
     #main()

#     sql = "SELECT * FROM Syms"
#     df = pd.read_sql_query(sql=sql, con=engine)
#     df.head()

# 読み込んだ文字列をイベントとしてあつかう実装となっている。
# 特定のsectionを検知すると特別なイベント(Header, Files)とし、そうでないものをcontentsイベントとしている。
# section(セクション):
#   - dlaファイル内に含まれる情報の区切り
#   - セクションには、親セクションがあり(Headerセクション)、その中に子セクションがある(Header以外のセクション)。
#   - Headerセクションは子セクションにならない。また、子セクション同士も入れ子にならない(親(Header)→子の1階層のみ)。
#   - セクションは、セクション名から始まって、次のセクション名 もしくは ファイル終端で終わる
#   - 各セクションの始まりは、正規表現^セクション名$で検出可能

#   セクション名:重要なものにのみ説明をつける
#     Header               : 親セクション。ファイルごとの区切り。子セクションに関する情報が含まれる
#       Files              : 子セクション。ファイル名、ファイルパスの情報。Filesの0:は、解析対象になっているソースコード自身。
#       Symbols            : 子セクション。構造体、列挙体、静的変数などに関する情報
#       Global Symbols     : 子セクション。グローバル変数や関数の情報(アドレス、メモリセクション(bss, rodata)など)
#       Cross References   : 子セクション。Global Symbolsを参照している具体的なリンク先(ファイル名、ライン、列の情報)と参照種類(定義、読み込み、書き込み)
#       Actual Calls       : 以降も子セクションだが、利用していないため省略
#       Auxs               
#       Frames             
#       Hash Define Hashs  
#       Hash Defines       
#       Include References 
#       Procs              
#       Static Calls       
#       Typedefs
 
# contens(コンテンツ):
#   - 情報の具体的な内容
#   - 正規表現^セクション名$で検出されなかったものはcontens
#   - セクション開始を検出していない場合もcontentsだが、


# 具体例
# Header
#     version = 33
#     magic = ..bof.D.3A.5Cuser.5Czf75944.5Cwork・・・
#     fileAdrMode = 32bit
# ・・・
# Files
# 0:   "Src\Appl\Audio\Common\AudioDiagTask.c" lc:C procs:(0,285) iLineMax:-1 iLSBase:0 chksum:-1 source-file:381 
# 1:   ".\Include\types.h" lc:C procs:(-1,-1) iLineMax:-1 iLSBase:0 chksum:-1 source-file:2 
# 2:   "D:\GHS\V800.V2013.5.5\comp_201355\ansi\string.h" lc:C procs:(-1,-1) iLineMax:-1 iLSBase:0 chksum:-1 source-file:3
# ・・・
# Global Symbols
# 3231:"unFlexRaySigBackup" 0xfef008a8, Extern  Bss C Union ref = 274 
# 3232:"usPeriodicAdcData" 0xfedd29da, Extern  Bss Array of C UShort [0..-1] 
# 3233:"usPeriodicAdcData1" 0xfedd2a16, Extern  Bss Array of C UShort [0..-1] 
# 3234:"g_st_adsp_ctrl_queue" 0xfedd0c74, Extern  Bss C Struct ref = 328 
# ・・・
# Symbols
# 0:   ("AudioDiagTask.c","Src\Appl\Audio\Common\AudioDiagTask.c") val:0xffffffff ind:(3231,-1) File-Begin  Info 
# 1:       "size_t" Typedef  Info C UInt 
# 2:       "ULONG" Typedef  Info C ULong 
# ・・・
# Cross References
# 0:   iSym:1 reftype:Definition file:3 line:50 col:27 
# 1:   iSym:1 reftype:Read file:2 line:79 col:15 
# 2:   iSym:1 reftype:Read file:2 line:82 col:15 
# 3:   iSym:1 reftype:Read file:2 line:83 col:15 
# 4:   iSym:1 reftype:Read file:2 line:84 col:15 