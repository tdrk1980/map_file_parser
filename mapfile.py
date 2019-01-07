# -*- coding: utf-8 -*-

from logging import getLogger, DEBUG, NullHandler, StreamHandler, FileHandler
selflogger = getLogger(__name__)
selflogger.setLevel(DEBUG)
selflogger.addHandler(NullHandler()) # 必要に応じてStremaHandlerなどを設定する
selflogger.propagate = False

import re
import types
import tqdm

def parse(fname, encoding="utf-8", callback=None, logger=None):
    r'''
    正規表現を利用して、マップファイルを解析する関数

    Parameters
    ----------
    fname : str
        マップファイルのファイル名。

    callback : function
        合致した内容を受け取る関数を設定する。
        引数には以下のdictが設定される。
        {"addr": int, "size":int}
     
    logger : logger
        デバッグログを出力するloggingモジュールのloggerインスタンス。
        基本的に設定しなくてOK。設定する場合は以下参照
        https://qiita.com/amedama/items/b856b2f30c2f38665701

    Notes
    -----
    正規表現に合致した内容は1件ずつコールバックされる。
    sizeが0以下のものはコールバックされない。
    
    サクラエディタで以下の正規表現で検索すると、マップファイルのどこにマッチするか具体的にわかる。
    (?P<section>\S+?) +(?P<addr>[0-9A-Fa-f]{8})\+(?P<size>[0-9A-Fa-f]{6}) (?P<sym>\S+)

    Examples
    --------
    名前付きキャプチャ(?P<section>など)でキャプチャされるものの例
    例：
    .rodata          000164d8+000040 _Com_TxModeInfo
    　↓
    section = .rodata ・・・ セクション名
    addr    = 000164d8 ・・・ アドレス
    size    = 000040 ・・・ サイズ(16進数)
    sym     = _Com_TxModeInfo ・・・ シンボル名(関数名、変数名)
    
    '''

    # loggerを設定(デフォルトは何も出力しない)
    log = logger or selflogger

    if not isinstance(callback, types.FunctionType) or not isinstance(callback, types.MethodType):
        pass
    else:
        log.error("callback should be FunctionType or MethodType")
        return

    # 利用する正規表現をコンパイルしておく
    expr = re.compile(r"(?P<sect>\S+?) +(?P<addr>[0-9A-Fa-f]{8})\+(?P<size>[0-9A-Fa-f]{6}) (?P<sym>\S+)")

    with open(fname, "r", encoding=encoding) as f:
        for s in tqdm.tqdm(f):
            s = s.strip()

            # 正規表現による解析
            m = expr.search(s)
            if m:
                # マッチしたものからセクション、アドレスなどを抜き出す
                sect = m.group("sect")
                size = int(m.group("size"),16)
                addr = int("0x" + m.group("addr"),16)
                sym  = m.group("sym")
                ret = {"sect":sect, "addr": addr, "size":size, "sym":sym}
                
                # sizeが0より大きいものをコールバックする 
                if size > 0:
                    callback(ret)
                else:
                    log.debug("size <= 0, ignored !! : " + str(ret))


if __name__ == '__main__':
    # 引数の解析
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("file", help="解析するマップファイル",  type=str, nargs=1)
    args = parser.parse_args()

    # デバッグログ出力の設定
    from logging import getLogger, DEBUG, StreamHandler
    logger = getLogger("test")
    logger.addHandler(StreamHandler())
    logger.setLevel(DEBUG)
    logger.propagate = False
    
    # 結果を受け取るコールバック関数の定義
    def result(dic):
        print(dic)
    
    # 解析開始
    parse(args.file[0], result, logger)
