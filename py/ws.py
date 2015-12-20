# encoding: UTF-8
import json
import time
import shelve
import os
import socket
from bottle import route,get, run, static_file,error,request
from bottle.ext.websocket import GeventWebSocketServer
from bottle.ext.websocket import websocket
from demoEngine import MainEngine
from string import lowercase as _chars
from time import sleep
from eventType import *

cs = set()
me = {}
STORE = "local_store"

@route('/css/<file_name>')
def get_css(file_name):
    return static_file(file_name,root = os.path.join(os.getcwd(),'css'))

@route('/ico/favicon.ico')
def get_ico():
    return static_file("ico.ico",root = os.path.join(os.getcwd(),'ico'))

@route('/src/<file_name>')
def get_src(file_name):
    return static_file(file_name,root = os.path.join(os.getcwd(),'src'))

@route('/src/<a>/<file_name>')
def get_src(a,file_name):
    return static_file(file_name,root = os.path.join(os.getcwd(),'src',a))

@route('/src/<a>/<b>/<file_name>')
def get_src(a,b,file_name):
    return static_file(file_name,root = os.path.join(os.getcwd(),'src',a,b))

@route('/src/<a>/<b>/<c>/<file_name>')
def get_src(a,b,c,file_name):
    return static_file(file_name,root = os.path.join(os.getcwd(),'src',a,b,c))

@route('/src/<a>/<b>/<c>/<d>/<file_name>')
def get_src(a,b,c,d,file_name):
    return static_file(file_name,root = os.path.join(os.getcwd(),'src',a,b,c,d))

@route('/py/<file_name>')
def get_py(file_name):
    return static_file(file_name,root = os.path.join(os.getcwd(),'py'))

def make_plus(accountid):
    o = ''
    for one in accountid:
        o = o+_chars[int(one)]
    return o

def get_server_ip():
    return socket.gethostbyname_ex(socket.gethostname())[-1]

def get_accounts():
    f = shelve.open(STORE)
    _out = f.get("accounts",{})
    f.close()
    return _out

class Bridge:
    _INSTRUMENT = "Saved_Instrument"
    def set_instrument(self,_dict):pass
    def get_instrument(self):pass
    def send_ws(self,event):
        try:
            _data = json.dumps(event.dict_,ensure_ascii=False)
            if event.type_ == EVENT_LOG:
                print(event.dict_['log'])
            for _ws in cs:
                try:
                    _ws.send(_data)
                except Exception,e:
                    print(_data,e)
        except Exception,e:
            print(event.dict_,e)


bg = Bridge()

def start_accounts(_acc):
    for k,v in _acc.items():
        _plus = make_plus(k)
        me[k] = MainEngine(v, _plus, bg)
        #me[k].set_instrument(v.get('instrument',[]))
        print("account "+k+" started")

def set_accounts(_acc):
    f = shelve.open(STORE)
    _out = {}
    for k,v in _acc.items():
        _out[k] = v
        _instrument = v['instrument'].split('+')
        _instrument.sort(reverse=True)
        if '' in _instrument:
            _pos = _instrument.index('')
            _out[k]['instrument'] = '+'.join(_instrument[:_pos])
    f['accounts'] = _out
    f.close()
    start_accounts(get_accounts())

print(u'可用地址: '+' '.join(get_server_ip()))
start_accounts(get_accounts())

@get('/monitor/')
def monitor():
    ips = '|'.join(get_server_ip())
    _t = int(time.time())
    return '''<!DOCTYPE html><html><head><link rel="stylesheet" href="/css/css.css?_=%d" /><link rel="shortcut icon" href="/ico/favicon.ico" type="image/x-icon" /><meta charset="utf-8"><script type="text/javascript" src="/src/brython.js?_=%d"></script><title>CTP监控终端</title></head><body onload="brython()"><script type="text/python" src="/py/monitor.py?_=%d"></script><main role="main" class="grid-container"><div class="grid-100 mobile-grid-100"><section class="example-block"><p><b>行情显示</b></p><div style="margin:10px;" id="marketdata"/><span class="dynamic-px-width"></span></section></div><div class="grid-100 mobile-grid-100"><section class="example-block"><p><b>帐户信息</b></p><div style="margin:10px;" id="account"/><span class="dynamic-px-width"></span></section></div><div class="grid-100 mobile-grid-100"><section class="example-block"><p><b>帐户持仓</b></p><div style="margin:10px;" id="position"/><span class="dynamic-px-width"></span></section></div><hr/><div class="grid-33 mobile-grid-33"><section class="example-block"><p><b>成交</b></p><div style="margin:10px;" id="trade"/><span class="dynamic-px-width"></span></section></div><div class="grid-33 mobile-grid-33"><section class="example-block"><p><b>报单</b></p><div style="margin:10px;" id="order"/><span class="dynamic-px-width"></span></section></div><div class="grid-33 mobile-grid-33"><section class="example-block"><p><b>日志</b></p><div style="margin:10px;" id="log"/><span class="dynamic-px-width"></span></section></div><input type="hidden" id="websocket_ip" value="%s"></main></body></html>'''%(_t,_t,_t,ips)

@get('/settings/')
def settings():
    ips = '|'.join(get_server_ip())
    _t = int(time.time())
    return '''<!DOCTYPE html><html><head><link rel="stylesheet" href="/css/css.css?_=%d" /><link rel="shortcut icon" href="/ico/favicon.ico" type="image/x-icon" /><meta charset="utf-8"><script type="text/javascript" src="/src/brython.js?_=%d"></script><title>CTP帐户管理</title></head><body onload="brython()"><script type="text/python" src="/py/settings.py?_=%d"></script><input type="hidden" id="websocket_ip" value="%s">
    <div id="console">获取帐户信息...请稍候...</div>
    <div id="ctp"></div>
    </body></html>'''%(_t,_t,_t,ips)

@get('/')
def index():
    return '''<!DOCTYPE html><html><head><link rel="stylesheet" href="/css/css.css" /><link rel="shortcut icon" href="/ico/favicon.ico" type="image/x-icon" /><meta charset="utf-8"></script><title>CTP终端</title></head><body><main role="main" class="grid-container"><div class="grid-100 mobile-grid-100"><section class="example-block"><div style="margin:10px;"/><a href="/monitor/" target="_blank">CTP监控界面</a><br/><a href="/settings/" target="_blank">CTP帐户管理</a></section></div></main></body></html>'''

def get_ctp_accounts(act):
    _dict = get_accounts()
    _out = {}
    _out['action'] = EVENT_CTPALL
    _out['data'] = _dict
    _rs = json.dumps(_out)
    for one in cs:
        one.send(_rs)

def update_ctp_accounts(act):
    _accs = act[-1]['data']
    set_accounts(_accs)

def empty_func(act):
    print(act)

funcs = {
    EVENT_EMPTY:empty_func,
    EVENT_CTPUPDATE:update_ctp_accounts,
    EVENT_CTPALL:get_ctp_accounts,
}

@get('/websocket', apply=[websocket])
def echo(ws):
    cs.add(ws)
    print(u'客户端'+str(ws)+u'连接至websocket')
    for one in me.values():
        one.set_ws(cs)
    while True:
        msg = ws.receive()
        if msg is not None:
            _dict = json.loads(msg)
            _type = _dict.get("action",EVENT_EMPTY)
            if _type in funcs:
                funcs[_type]((msg,_dict))
            else:
                empty_func(msg)
        else: break
    cs.remove(ws)
    print(u'客户端'+str(ws)+u'断开连接')
    for one in me.values():
        one.set_ws(cs)
