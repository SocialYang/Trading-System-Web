from browser import document, alert, html, websocket, timer, window
from browser.local_storage import storage
import json,time,datetime
from browser.timer import request_animation_frame as raf
from eventType import *

_TARGET_COLOR = 240 # 150
_background={}
count = 100

def width_label(c,width):
    s= html.LABEL(c)
    s.style={"display":"inline-block","width":"%dpx"%width}
    return s

def change_color(id):
    global _background
    _background[id] = _TARGET_COLOR #240 is close, 150 is open

def add_log(content):
    _doc = document['log']
    _id = "log{}".format(time.time())
    _content = html.LABEL(str(datetime.datetime.now())[11:19]+" "+content)
    some = html.DIV(_content,id=_id)
    some.style={"text-align":"left"}
    _l = _doc.children
    _doc.clear()
    _l=[some]+_l
    for one in _l[:count]:
        _doc<=one
    change_color(_id)

if 'ctp_server' in storage:
    add_log("服务器地址:"+storage['ctp_server'])
    address = 'ws://'+storage['ctp_server']+":9789/websocket"
else:
    add_log("服务器地址:本地")
    address = 'ws://localhost:9789/websocket'

class AccManager:
    def __init__(self):
        add_log("账户管理器启动")
    def __del__(self):
        add_log("账户管理器退出")


ws = websocket.WebSocket(address)
idTimer = 1

def event_log(_msg):
    add_log('['+_msg['_account_']+'] '+_msg['log'])

def event_product(_msg):
    _doc = document['marketdata']
    _dict = _msg['data']
    storage['product_list'] = json.dumps(_dict.keys())
    add_log(str(_dict))
    ws.send("ws_getinstrument=IF_master")

DirectionDict = {"0":"买","1":"卖"}
DirectionStyle = {"0":{"color":"red"},"1":{"color":"green"},"2":{"color":"red"},"3":{"color":"green"}}
OffsetFlagDict = {"0":"开仓","1":"平仓","2":"强平","3":"平今仓","4":"平昨仓","5":"强减","6":"本地强平"}
Orders = []

def event_order(_msg):
    global Orders
    _doc = document['order']
    _dict = _msg['data']
    _id = "order_{}_{}".format(_msg['_account_'],_dict['OrderRef'])
    _str = str(datetime.datetime.now())[11:19]+" [ {} ] {} 报{}价:{} {} 手数:{} {}".format(_msg['_account_'],_dict['InstrumentID'],DirectionDict.get(_dict['Direction'],"未知方向"),'%.2f'%float(_dict['LimitPrice']),OffsetFlagDict.get(_dict['CombOffsetFlag'],"未知开平"),_dict['VolumeTotalOriginal'],_dict['StatusMsg'])
    _content = html.LABEL(_str)
    _content.style = DirectionStyle.get(_dict['Direction'],{})
    some = html.DIV(_content,id=_id)
    some.style={"text-align":"left"}
    if Orders and Orders[0].id == _id:
        Orders = [some]+Orders[1:count]
    else:
        Orders = [some]+Orders[:count]
    _doc.clear()
    for one in Orders:
        _doc <= one
        change_color(_id)

Trades = []
def event_trade(_msg):
    global Trades
    _doc = document['trade']
    _dict = _msg['data']
    _id = "trade_{}_{}".format(_msg['_account_'],_dict['OrderRef'])
    _str = str(datetime.datetime.now())[11:19]+" [ {} ] {} {} {} 成交手数:{} 成交价:{}".format(_msg['_account_'],_dict['InstrumentID'],DirectionDict.get(_dict['Direction'],"未知方向"),OffsetFlagDict.get(_dict['OffsetFlag'],"未知开平"),_dict['Volume'],'%.2f'%float(_dict['Price']))
    _content = html.LABEL(_str)
    _content.style = DirectionStyle.get(_dict['Direction'],{})
    some = html.DIV(_content,id=_id)
    some.style={"text-align":"left"}
    if Trades and Trades[0].id == _id:
        Trades = [some]+Trades[1:count]
    else:
        Trades = [some]+Trades[:count]
    _doc.clear()
    for one in Trades:
        _doc <= one
    change_color(_id)

Ticks = []
def event_tick(_msg):
    global Ticks
    _doc = document['marketdata']
    _l = _doc.children
    _data = _msg['data']
    _id = "tick_{}".format(_data['InstrumentID'])
    _content = width_label(_data['InstrumentID'],100)
    _content += width_label("叫卖1",30)+width_label(_data["AskPrice1"],50)+width_label(_data["AskVolume1"],50)
    _content += width_label("叫买1",50)+width_label(_data["BidPrice1"],50)+width_label(_data["BidVolume1"],50)
    _content += width_label("最新价",40)
    _content += width_label(_data["LastPrice"],50)
    _content += width_label("持仓量",40)
    _content += width_label(_data["Volume"],50)
    _content += width_label(_data["UpdateTime"],50)
    some = html.DIV(_content,id=_id)
    some.style={"text-align":"left"}
    haved = False
    _out = []
    for one in Ticks:
        if one.id == _id:
            haved = True
            _out = [some]+_out
        else:
            _out = [one]+_out
    if not haved:
        _out = [some]+_out
    Ticks = _out
    _doc.clear()
    for one in Ticks:
        _doc <= one
    change_color(_id)

PosAccount = set()
PosInst = set()
PosDir = ["2","3"]
PosDict = {}

def event_position(_msg):
    global PosAccount
    global PosInst
    global PosDir
    global PosDict
    _doc = document['position']
    _dict = _msg['data']
    _id = "position_{}_{}_{}".format(_msg['_account_'],_dict['InstrumentID'],_dict['PosiDirection'])
    PosAccount.add(_msg['_account_'])
    PosInst.add(_dict['InstrumentID'])
    _str = ''
    _str += width_label("帐号",30)
    _str += width_label(_msg['_account_'],80)
    _str += width_label("合约",30)
    _str += width_label(_dict['InstrumentID'],80)
    _str += width_label("今仓",30)
    _str += width_label(_dict['TodayPosition'],80)
    _str += width_label("昨仓",50)
    _str += width_label(_dict['YdPosition'],80)
    _str += width_label("总仓",50)
    _str += width_label(_dict['Position'],80)
    _content = html.LABEL(_str)
    _content.style = DirectionStyle.get(_dict['PosiDirection'],{})
    some = html.DIV(_content,id=_id)
    some.style={"text-align":"left"}
    PosDict[_id] = some
    _doc.clear()
    for pac in PosAccount:
        for pinst in PosInst:
            for pdir in PosDir:
                _pid = "position_{}_{}_{}".format(pac,pinst,pdir)
                if _pid in PosDict:
                    _doc <= PosDict[_pid]
    change_color(_id)

Accounts = set()
AccDict = {}
def event_account(_msg):
    global Accounts
    global AccDict
    _doc = document['account']
    _dict = _msg['data']
    _id = "account_{}".format(_msg['_account_'])
    Accounts.add(_id)
    _str = ''
    _str+= width_label("帐号",30)
    _str+= width_label(_msg['_account_'],80)
    _str+= width_label("持仓盈亏",50)
    _str+= width_label('%.2f'%float(_dict['PositionProfit']),80)
    _str+= width_label("可用",30)
    _str+= width_label('%.2f'%float(_dict['Available']),80)
    _str+= width_label("净值",30)
    _str+= width_label('%.2f'%float(_dict['Balance']),80)
    _content = html.LABEL(_str)
    some = html.DIV(_content,id=_id)
    some.style={"text-align":"left"}
    AccDict[_id] = some
    _doc.clear()
    for one in Accounts:
        _doc <= AccDict[one]
    change_color(_id)

funcs={
            EVENT_LOG:event_log,
            EVENT_TICK:event_tick,
            EVENT_ORDER:event_order,
            EVENT_TRADE:event_trade,
            EVENT_ACCOUNT:event_account,
            EVENT_POSITION:event_position,
            EVENT_PRODUCT:event_product,
    }

def ws_msg(ev):
    _msg = json.loads(ev.data)
    _type = _msg.get('_type_','EmptyType')
    if _type in funcs:
        funcs[_type](_msg)
    else:
        add_log(ev.data)

rafId = 0
def loop():
    global rafId,_background
    if _background:
        _all = _background.items()
        _background = {}
        for k,v in _all:
            if v<240:
                document[k].set_style({"background":"#{:x}{:x}{:x}".format(v,v,v)})
                _background[k] = v+1
                #rafId = raf(loop)

def step_one():
    if 'ctp_account' in storage:
        _acc = json.loads(storage['ctp_account'])
        if _acc:
            ws.send("ws_ctpaccount="+storage['ctp_account'])
            timer.set_timeout(step_two, 1000)
        else:
            add_log(html.A("请先设置ctp信息",href="settings.html"))
    else:
        add_log(html.A("请先设置ctp信息",href="settings.html"))

def step_two():
    add_log("确认帐户信息")
    document['marketdata'].clear()
    document['account'].clear()
    document['position'].clear()
    document['trade'].clear()
    document['order'].clear()
    timer.set_timeout(step_three, 1000)

def step_three():
    add_log("启动循环消息")
    timer.set_timeout(loop, 1000)

def reconnect():
    add_log("重连ing")
    window.location.reload()

def ws_open():
    add_log("连接服务器端")
    timer.set_timeout(step_one, 1000)

def ws_error():
    add_log("!!!websocket连接报错!!!")

def ws_disconnected():
    add_log("服务器端断开连接,3秒后尝试重连")
    idTimer = timer.set_timeout(reconnect, 3000)

ws.bind('message',ws_msg)
ws.bind('close',ws_disconnected)
ws.bind('open',ws_open)
ws.bind('error',ws_error)
document['restart'].bind('click',show_storage)
