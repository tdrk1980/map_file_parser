# -*- coding: utf-8 -*--

from logging import getLogger, DEBUG, NullHandler, StreamHandler, FileHandler
selflogger = getLogger(__name__)
selflogger.setLevel(DEBUG)
selflogger.addHandler(NullHandler()) # 必要に応じてStremaHandlerなどを設定する
selflogger.propagate = False

# dlaファイルからは、・・・正確にはgdump.exeにかけてテキスト化したファイル
# - 変数、関数が定義されているファイル名
# - シンボル名(関数名、変数名)
# - ROM(.text, .rodata) or RAM(.bss, .data)の区別
# が取得できる。
# ※ それ以外にも情報はとれそうだが調査してないので解析対象にしていない
# https://www.ibm.com/developerworks/jp/linux/library/l-python-state/index.html
# dlaファイル自体については、doc/dlafile.md参照 (実装的にはparse関数参照)
# いくつかの理由で文脈判断やファイル名保持が必要になり、parse関数では状態を持っている。
# 
# - 複数のファイルの情報が結合されていること
# - 欲しい情報の順序が意図通りではないこと
#  ※ ファイル名とともにシンボル名がとればいいが、そうなっていない。
#  ※ たとえば、ファイル名を保持していないと
#  ※ xxxx.cに定義されたstatic int aなのか、yyyy.cのstatic int aなのか判別できなくなる。


import ret
import pathlib
import transitions

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
        {"addr":str, "isym":str, "name":str, "scope":str, "sect":str}

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
        return {"name": m.group("name"), "isym": m.group("isym"), "addr": m.group("addr"), "scope": m.group("scope"), "sect": m.group("sect")}
    else:
        return None



# Cross Referencesセクションのシンボルリファレンス情報を取得するための正規表現
expr_isym_reftype = r"^\d+?: *iSym:(?P<isym>\d+?) *reftype:(?P<reftype>.+?) file:(?P<file>\d+?) line:(?P<line>\d+?) col:(?P<col>\d+?)"
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
        {"col": str, "file": str, "isym": str, "line": str, "reftype": str}

    Notes
    -----
    利用する正規表現
    ^\d+?: *iSym:(?P<isym>\d+?) *reftype:(?P<reftype>.+?) file:(?P<file>\d+?) line:(?P<line>\d+?) col:(?P<col>\d+?)
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
        return {"isym": m.group("isym"), "reftype": m.group("reftype"), "file": m.group("file"), "line": m.group("line"), "col": m.group("col")}
    else:
        return None


def parse(fname, cb_map=None, cb_sym=None, cb_cref=None):
    with open(fname, "r") as f:
        for s in f:
            ev = parse_line(s)
            print(ev)