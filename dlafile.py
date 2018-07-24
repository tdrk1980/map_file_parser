# -*- coding: utf-8 -*--

from logging import getLogger, DEBUG, NullHandler, StreamHandler, FileHandler
import re
import types
import pathlib
# import transitions # 将来的に利用するかも

selflogger = getLogger(__name__)
selflogger.setLevel(DEBUG)
selflogger.addHandler(NullHandler()) # 必要に応じてStremaHandlerなどを設定する
selflogger.propagate = False

### dlaファイルについて
# dlaファイルからは、
# - 変数、関数が定義されているファイル名
# - シンボル名(関数名、変数名)
# - ROM(.text, .rodata) or RAM(.bss, .data)の区別
# が取得できます。
# ※ 正確にはgdump.exeにかけてテキスト化したファイル
# ※ それ以外にも情報はとれそうだが調査してない。
# 
# dlaファイルは、ステートフル・テキスト・ファイルなので状態を持って処理する必要があります。
# ファイル構造や状態の詳細は、doc/dlafile.mdを参照
# 実装は、parse関数を参照
# 
# 参考：テキスト処理用ステート・マシン - IBM
# https://www.ibm.com/developerworks/jp/linux/library/l-python-state/index.html 
###

# ファイルセクション(Headerなどのキーワード部分)にマッチする正規表現
expr_line = r"(?P<file_section>^Actual Calls$|^Auxs$|^Cross References$|^Files$|^Frames$|^Global Symbols$|^Hash Define Hashs$|^Hash Defines$|^Header$|^Include References$|^Procs$|^Static Calls$|^Symbols$|^Typedefs$)"
re_line = re.compile(expr_line)

def parse_line(s):
    r'''
    dlaファイルの行を解析し、ファイルセクション情報もしくはコンテンツ情報を返す。

    Parameters
    ----------
    s : str
        dlaファイルの各行

    Returns
    -------
    result : dict
        キー
          file_section_info : ファイルセクション情報
          content_info : コンテンツ情報(非ファイルセクション情報)
        有効な情報にはstrが、無効な情報にはNoneが排他的に格納される。
        {'content_info': str or None, 'file_section_info': str or None

    Notes
    -----
    ファイルセクション情報の定義：
        以下の正規表現にマッチする部分。
        ^Actual Calls$|^Auxs$|^Cross References$|^Files$|^Frames$|^Global Symbols$|^Hash Define Hashs$|^Hash Defines$|^Header$|^Include References$|^Procs$|^Static Calls$|^Symbols$|^Typedefs$
    コンテンツ情報の定義：
      ファイルセクション情報以外すべて

    Examples
    --------
    In [18]: parse_line("Header")
    Out[18]: {'content_info': None, 'file_section_info': 'Header'}

    In [19]: parse_line("245: iSym:2 reftype:Read file:13 line:346 col:1")
    Out[19]: {'content_info': '245: iSym:2 reftype:Read file:13 line:346 col:1', 'file_section_info': None}
    '''

    m = re_line.search(s.strip())
    if m:
        result = {"file_section_info":m.group("file_section"), "content_info":None}   
    else:
        result = {"file_section_info":None, "content_info":s}
    return result



# Cソースファイルのパスを取得する正規表現
expr_c_source_file_path = r"^(0:) *\"(?P<c_source_file_path>.+?)\" lc:C .*"
re_c_source_file_path = re.compile(expr_c_source_file_path)

def get_c_source_file_path(s):
    r'''
    文字列を解析し、Cソースファイルのパスを返す。
    
    Parameters
    ----------
    s : str

    Returns
    -------
    c_source_file_path : str or None
        Cソースファイルのパスが見つかった場合はstrを返す。ビルドしたフォルダをトップとする相対パスになっていることに注意する。
        見つからなかった場合は、Noneを返す。

    Notes
    -----
    正規表現の名前付きキャプチャ(c_source_file_path)の部分がCソースファイルのパス。
    ^(0:) *\"(?P<c_source_file_path>.+?)\" lc:C .*

    Examples
    --------
    In [11]: get_c_source_file_path("0:   \"root\\a\\b\\c\\d\\e.c\" lc:C procs:(0,46) iLineMax:-1 iLSBase:0 chksum:-1 source-file:290")
    Out[11]: 'root\\a\\b\\c\\d\\e.c'
    '''
    m = re_c_source_file_path.search(s.strip())
    if m:
        return m.group("c_source_file_path")
    else:
        return None


# 変数シンボル情報を取得するための正規表現
expr_variable_symbol_info = r"^(?P<isym>\d+?): *\"(?P<name>.+?)\" *(?P<addr>0x[0-9A-Fa-f]{8}), (?P<scope>.+?)  (?P<sect>.+?) "
re_variable_symbol_info = re.compile(expr_variable_symbol_info)

def get_variable_symbol_info(s):
    r'''
    文字列を解析し、変数シンボル情報(dict)を返す。

    Parameters
    ----------
    s : str

    Returns
    -------
    variable_symbol_info : dict or None
        変数シンボル情報が見つかった場合は、以下のdictを返す。見つからなかった場合はNoneを返す
        {"addr":int, "isym":int, "name":str, "scope":str, "sect":str}

    Notes
    -----
    利用する正規表現
    ^(?P<isym>\d+?): *\"(?P<name>.+?)\" *(?P<addr>0x[0-9A-Fa-f]{8}), (?P<scope>.+?)  (?P<sect>.+?) 
        addr ・・・アドレス
        isym ・・・シンボル番号(コンパイラが付与するシンボルを識別するための番号。get_isym_reftype()と組み合わせて利用する。)
        name ・・・シンボル名(変数名)
        scope・・・変数のスコープ(Static, Extern)
        sect ・・・RAMのセクション情報(Bss, Data, Data-In-Text)
                   .bssなどとの対応関係は、
                   Bss <--> .bss
                   Data <--> .data
                   Data-In-Text <--> .rodata
    ※関数シンボル情報は取っていない。(この正規表現では取れない。)

    Examples
    -----
    In [13]: get_variable_symbol_info("331:             \"uc_err_buf\" 0xfee005b0, Static  Bss Array of C Typedef ref = 3 [0..15]")
    Out[13]: 
    {'addr': '0xfee005b0',
    'isym': '331',
    'name': 'uc_err_buf',
    'scope': 'Static',
    'sect': 'Bss'}
    '''
    m = re_variable_symbol_info.search(s)
    if m:
        return {"addr": int(m.group("addr"),16), "isym": int(m.group("isym"),16), "name": m.group("name"), "scope": m.group("scope"), "sect": m.group("sect")}
    else:
        return None



# Cross Referencesセクションのシンボルリファレンス情報を取得するための正規表現
expr_isym_reftype = r"^\d+?: *iSym:(?P<isym>\d+?) *reftype:(?P<reftype>.+?) file:(?P<file>\d+?) line:(?P<line>\d+?) col:(?P<col>\d+)"
re_isym_reftype = re.compile(expr_isym_reftype)

def get_isym_reftype(s):
    r'''
    文字列を解析し、シンボルリファレンス情報(dict)を返す。

    Parameters
    ----------
    s : str

    Returns
    -------
    isym_reftype : dict or None
        シンボルリファレンス情報が見つかった場合は、以下のdictを返す。見つからなかった場合はNoneを返す。
        {"col": int, "file": str, "isym": int, "line": int, "reftype": str}

    Notes
    -----
    利用する正規表現
    ^\d+?: *iSym:(?P<isym>\d+?) *reftype:(?P<reftype>.+?) file:(?P<file>\d+?) line:(?P<line>\d+?) col:(?P<col>\d+)
        isym・・・シンボル番号(コンパイラが付与するシンボルを識別するための番号。get_variable_symbol_info()と組み合わせて利用する。)
        reftype・・・シンボルに対して何をしているかを示す文字列。以下のタイプがある。
                    Address-Taken : アドレス取得(&)
                    Declaration : 宣言
                    Definition : 定義
                    Read : 読み込み
                    Write : 書き込み
                    Read,Write : 読み書き
        file・・・ファイルの番号(Filesセクションの番号)
        line・・・行
        col・・・カラム。列

    Examples
    -----
    In [21]: get_isym_reftype("64:  iSym:1 reftype:Read file:30 line:193 col:9")
    Out[21]: {'col': '9', 'file': '30', 'isym': '1', 'line': '193', 'reftype': 'Read'}

    '''
    m = re_isym_reftype.search(s)
    if m:
        return {"col": int(m.group("col")), "file": m.group("file"), "isym": int(m.group("isym")), "line": int(m.group("line")), "reftype": m.group("reftype") }
    else:
        return None


def parse(fname, encoding="utf-8", callback_symbol=None, callback_crossref=None, logger=selflogger):
    r'''
    テキスト化された.dlaを解析する

    Parameters
    ----------
    fname : str
        テキスト化された.dlaのファイル名

    callback_symbol : function or None
        シンボル情報を受け取る関数

    callback_crossref : function or None
        クロスリファレンス情報を受け取る関数(シンボル情報とisymによって結合できる)

    logger : logger
        デバッグログを出力するloggingモジュールのloggerインスタンス。
        基本的に設定しなくてOK。設定する場合は以下参照
        https://qiita.com/amedama/items/b856b2f30c2f38665701
    Notes
    -----
    T.B.D

    Examples
    -----
    T.B.D
    '''
    # loggerを設定(デフォルトは何も出力しない)
    log = logger or selflogger

    if isinstance(callback_symbol, types.FunctionType) or isinstance(callback_symbol, types.MethodType):
        pass
    else:
        log.error("callback_symbol should be FunctionType or Methodtype")
        return

    if isinstance(callback_crossref, types.FunctionType) or isinstance(callback_crossref, types.MethodType):
        pass
    else:
        log.error("callback_crossref should be FunctionType or Methodtype")
        return

    c_source_file_path = None
    with open(fname, "r", encoding=encoding) as f:
        cur_state = nxt_state = "init"
        
        for i, s in enumerate(f, 1):
            cur_state = nxt_state
            ev = parse_line(s)
            log.debug(f"{i}:{s} ==> ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}")

            if cur_state == "init":
                if ev["file_section_info"] in ["Files"]:
                    c_source_file_path = None
                    nxt_state = "parsingFiles"
                    log.info(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}")
                else:
                    log.debug(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}")
                    pass

            elif cur_state == "parsingFiles":
                if ev["content_info"]:
                    c_source_file_path = get_c_source_file_path(ev["content_info"])
                    if c_source_file_path:
                        nxt_state = "joinSymbolsCrossRef"
                        log.info(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}")
                    else:
                        log.debug(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}")
                        pass
                else:
                    nxt_state = "init"
                    log.debug(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}")

            elif cur_state in ["joinSymbolsCrossRef"]:
                if ev["file_section_info"] in ["Symbols", "Global Symbols"]:
                    nxt_state = "parseSymbols"
                    log.info(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}")
                elif ev["file_section_info"] in ["Cross References"]:
                    nxt_state = "parseCrossReferences"
                    log.info(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}")
                elif ev["file_section_info"] in ["Header"]:
                    nxt_state = "init"
                    log.info(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}")
                else:
                    log.debug(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}")
                    pass

            elif cur_state in ["parseSymbols"]:
                if ev["content_info"]:
                    sym = get_variable_symbol_info(ev["content_info"])
                    if sym:
                        symdic = {"file":c_source_file_path, "name":sym["name"], "addr": sym["addr"], "isym":sym["isym"], "scope": sym["scope"], "sect": sym["sect"]}
                        callback_symbol(symdic)
                        log.info(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}, symdic={symdic}")
                    else:
                        log.debug(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}")
                        pass
                elif ev["file_section_info"] in ["Symbols", "Global Symbols"]:
                    log.debug(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}")
                    pass
                elif ev["file_section_info"] in ["Header"]:
                    nxt_state = "init"
                    log.debug(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}")
                else:
                    nxt_state = "joinSymbolsCrossRef"
                    log.debug(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}")

            elif cur_state in ["parseCrossReferences"]:
                if ev["content_info"]:
                    cr = get_isym_reftype(ev["content_info"])
                    if cr:
                        crdic = {"file":c_source_file_path, "isym": cr["isym"], "reftype": cr["reftype"], "ifile": cr["file"], "line": cr["line"], "col": cr["col"]}
                        callback_crossref(crdic)
                        log.info(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}, crdic={crdic}")
                    else:
                        log.debug(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}")
                else:
                    nxt_state = "init"
                    log.debug(f"ev={ev}, cur_state={cur_state}, nxt_state={nxt_state}")

if __name__ == '__main__':
    # 引数の解析
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("file", help="解析するdlaファイル",  type=str, nargs=1)
    args = parser.parse_args()

    # デバッグログ出力の設定
    from logging import getLogger, DEBUG, StreamHandler
    logger = getLogger("test")
    logger.addHandler(StreamHandler())
    logger.setLevel(DEBUG)
    logger.propagate = False

    def symbol(item):
        print(item)

    def crossref(item):
        print(item)

    # 解析開始
    parse(args.file[0], callback_symbol=symbol, callback_crossref=crossref, logger=None)
