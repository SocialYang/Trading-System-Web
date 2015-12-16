# encoding: UTF-8

"""
该文件中包含的是交易平台的中间层，
将API和事件引擎包装到一个主引擎类中，便于管理。

当客户想采用服务器-客户机模式，实现交易功能放在托管机房，
而图形控制功能在本地电脑时，该主引擎负责实现远程通讯。
"""
from datetime import date
from time import sleep,time
import shelve
import json
import zmq

#from PyQt4 import QtCore

from demoApi import *
from eventEngine import EventEngine
from threading import Lock

class SymbolOrdersManager:
    def __init__(self,symbol,data,me):
        self.symbol = symbol
        self.data = data
        self.me = me
        self.__lock = Lock()
        self.__maxRetry = 5
        self.__status = {}
        self.__stlist = set()
        self.__orders = {}
        self.__hold = 0
        self.__price = {}
        print("Symbol:",self.data)
    def hold(self,vol):
        self.__hold = vol
    def openPosition(self,tr,volume):
        event = Event(type_=EVENT_LOG)
        log = u'开仓[%s] %d %d'%(self.symbol,tr,volume)
        event.dict_['log'] = log
        self.me.ee.put(event)
        self.me.countGet = -2
        offset = defineDict['THOST_FTDC_OF_Open']
        pricetype = defineDict['THOST_FTDC_OPT_LimitPrice']
        if tr>0:
            price = self.__price['ask']+self.data['PriceTick']*2.0
            direction = defineDict["THOST_FTDC_D_Buy"]
        else:
            price = self.__price['bid']-self.data['PriceTick']*2.0
            direction = defineDict["THOST_FTDC_D_Sell"]
        exchangeid = self.data["ExchangeID"]
        _ref = self.me.td.sendOrder(self.symbol,exchangeid,price,pricetype,volume,direction,offset)
        self.__orders[_ref] = (self.symbol,exchangeid,price,pricetype,volume,direction,offset,0)
    def closePosition(self,tr,volume):
        event = Event(type_=EVENT_LOG)
        log = u'平仓[%s] %d %d'%(self.symbol,tr,volume)
        event.dict_['log'] = log
        self.me.ee.put(event)
        self.me.countGet = -2
        offset = defineDict['THOST_FTDC_OF_Close']
        pricetype = defineDict['THOST_FTDC_OPT_LimitPrice']
        if tr<0:
            price = self.__price['ask']+self.data['PriceTick']*2.0
            direction = defineDict["THOST_FTDC_D_Buy"]
        else:
            price = self.__price['bid']-self.data['PriceTick']*2.0
            direction = defineDict["THOST_FTDC_D_Sell"]
        exchangeid = self.data["ExchangeID"]
        _ref = self.me.td.sendOrder(self.symbol,exchangeid,price,pricetype,volume,direction,offset)
        self.__orders[_ref] = (self.symbol,exchangeid,price,pricetype,volume,direction,offset,0)
    def closeTodayPosition(self,tr,volume):
        event = Event(type_=EVENT_LOG)
        log = u'平今仓[%s] %d %d'%(self.symbol,tr,volume)
        event.dict_['log'] = log
        self.me.ee.put(event)
        self.me.countGet = -2
        offset = defineDict['THOST_FTDC_OF_CloseToday']
        pricetype = defineDict['THOST_FTDC_OPT_LimitPrice']
        if tr<0:
            price = self.__price['ask']+self.data['PriceTick']*2.0
            direction = defineDict["THOST_FTDC_D_Buy"]
        else:
            price = self.__price['bid']-self.data['PriceTick']*2.0
            direction = defineDict["THOST_FTDC_D_Sell"]
        exchangeid = self.data["ExchangeID"]
        _ref = self.me.td.sendOrder(self.symbol,exchangeid,price,pricetype,volume,direction,offset)
        self.__orders[_ref] = (self.symbol,exchangeid,price,pricetype,volume,direction,offset,0)
    def ontrade(self,event):pass
    def onorder(self,event):#pass
        _data = event.dict_['data']
        if _data['OrderStatus'] == '5':
            if int(_data['OrderRef']) in self.__orders:
                _saved = self.__orders.pop(int(_data['OrderRef']))
            else:
                return 0
            if _saved[-1]>=self.__maxRetry:
                return 0
            event = Event(type_=EVENT_LOG)
            log = u'未成交已撤单，补单'
            event.dict_['log'] = log
            self.me.ee.put(event)
            if _saved[5] == defineDict["THOST_FTDC_D_Buy"]:
                price = float(_saved[2])+self.data['PriceTick']
            elif _saved[5] == defineDict["THOST_FTDC_D_Sell"]:
                price = float(_saved[2])-self.data['PriceTick']
            else:
                price = -1
                print("demoEngine.py SymbolOrdersManager onorder not found THOST_FTDC_D")
            _ref = self.me.td.sendOrder(_saved[0],_saved[1],price,_saved[3],_saved[4],_saved[5],_saved[6])
            self.__orders[_ref] = (_saved[0],_saved[1],price,_saved[3],_saved[4],_saved[5],_saved[6],_saved[-1]+1)
        elif _data['OrderStatus'] == '2':
            if int(_data['OrderRef']) in self.__orders:
                _saved = self.__orders.pop(int(_data['OrderRef']))
            else:
                return 0
            if _saved[-1]>=self.__maxRetry:
                return 0
            event = Event(type_=EVENT_LOG)
            log = u'部分成交，其余已撤单，补单'
            event.dict_['log'] = log
            self.me.ee.put(event)
            if _saved[5] == defineDict["THOST_FTDC_D_Buy"]:
                price = float(_saved[2])+self.data['PriceTick']
            elif _saved[5] == defineDict["THOST_FTDC_D_Sell"]:
                price = float(_saved[2])-self.data['PriceTick']
            else:
                price = -1
                print("demoEngine.py SymbolOrdersManager onorder not found THOST_FTDC_D")
            _todo = _saved[4]-_data['VolumeTraded']
            _ref = self.me.td.sendOrder(_saved[0],_saved[1],price,_saved[3],_todo,_saved[5],_saved[6])
            self.__orders[_ref] = (_saved[0],_saved[1],price,_saved[3],_todo,_saved[5],_saved[6],_saved[-1]+1)
        elif _data['OrderStatus'] == '0':
            event = Event(type_=EVENT_LOG)
            log = u'全部成交'
            event.dict_['log'] = log
            self.me.ee.put(event)
            if int(_data['OrderRef']) in self.__orders:
                self.__orders.pop(int(_data['OrderRef']))
    def ontick(self,event):#pass
        _data = event.dict_['data']
        _ask = _data['AskPrice1']
        _bid = _data['BidPrice1']
        _symbol = _data['InstrumentID']
        _exchange =  self.data.get("ExchangeID",'')
        self.__price = {"ask":_ask,"bid":_bid,"price":(_ask+_bid)/2.0}
        with self.__lock:
            if self.me.socket:
                self.me.socket.send(bytes(json.dumps({"data":self.__price['price'],"symbol":self.symbol})))
                if self.symbol not in self.me.subInstrument:
                    return  #   非订阅合约
            else:
                return
            self.__hold = int(self.me.socket.recv())
            if len(self.__orders)>0:
                print(self.symbol,self.__orders)
            else:
                _long       =   defineDict["THOST_FTDC_PD_Long"]
                _short      =   defineDict["THOST_FTDC_PD_Short"]
                long_st     =   self.__status.get(_long,{})
                short_st    =   self.__status.get(_short,{})

                print(self.symbol,self.__status,"BEFORE",self.__hold)

                def do_it(_todo,_pass,_reverse,d_pass,d_reverse):
                    if self.__status.get(_reverse,{}).get("2",0)>0:
                        self.closePosition(d_reverse,self.__status[_reverse]['2'])
                    if self.__status.get(_reverse,{}).get("1",0)>0:
                        self.closeTodayPosition(d_reverse,self.__status[_reverse]['1'])

                    self.__status[_reverse] = {}

                    _old = self.__status.get(_pass,{})
                    _old_old = _old.get('2',0)
                    _old_today = _old.get('1',0)
                    _haved = sum(_old.values())

                    if _todo>_haved:
                        self.openPosition(d_pass,_todo-_haved)
                        _old['1'] = _old_today+(_todo-_haved)
                    elif _todo<_haved:
                        if _todo-_haved > _old_old:
                            # 昨仓全平 今仓平一部分
                            self.closePosition(_pass,_old_old)
                            _old['2'] = 0
                            self.closeTodayPosition(_pass,_todo-_haved-_old_old)
                            _old['1'] = _old_today - (_todo-_haved-_old_old)
                        elif _todo-_haved == _old_old:
                            # 昨仓全平
                            self.closePosition(_pass,_old_old)
                            _old['2'] = 0
                        else:
                            # 昨仓平一部分
                            self.closePosition(_pass,_todo-_haved)
                            _old['2'] = _old_old - (_todo-_haved)

                    self.__status[_pass] = _old

                if self.__hold==0:
                    if long_st.get("2",0)>0:
                        self.closePosition(1,long_st['2'])
                    if long_st.get("1",0)>0:
                        self.closeTodayPosition(1,long_st['1'])
                    if short_st.get("2",0)>0:
                        self.closePosition(-1,short_st['2'])
                    if short_st.get("1",0)>0:
                        self.closeTodayPosition(-1,short_st['1'])
                    self.__status = {}
                elif self.__hold>0:
                    _todo = abs(self.__hold)
                    _pass = _long
                    _reverse = _short
                    d_pass = 1
                    d_reverse = -1
                    do_it(_todo,_pass,_reverse,d_pass,d_reverse)
                else:
                    _todo = abs(self.__hold)
                    _pass = _short
                    _reverse = _long
                    d_pass = -1
                    d_reverse = 1
                    do_it(_todo,_pass,_reverse,d_pass,d_reverse)

                print(self.symbol,self.__status,"AFTER",self.__hold)
    def onposi(self,event):#pass
        _data = event.dict_['data']
        _dir = _data['PosiDirection']
        _date = _data['PositionDate']
        _vol = _data['Position']
        with self.__lock:
            _old = self.__status.get(_dir,{})
            _old[_date] = _vol
            self.__status[_dir] = _old
            if (_dir,_date) in self.__stlist:
                for k,v in self.__status:
                    _dict = {}
                    _dict['InstrumentID'] = self.symbol
                    _dict['PosiDirection'] = k
                    _dict['TodayPosition'] = v.get("1",0)
                    _dict['YdPosition'] = v.get("2",0)
                    _dict['Position'] = _dict['TodayPosition']+_dict['YdPosition']
                    event = Event(type_=EVENT_POSIALL)
                    event.dict_['data'] = _dict
                    self.me.ee.put(event)
                self.__stlist = set()
                self.__stlist.add((_dir,_date))
            else:
                self.__stlist.add((_dir,_date))

    def get_price(self):
        return self.__price

########################################################################
class MainEngine:
    """主引擎，负责对API的调度"""

    #----------------------------------------------------------------------
    def __init__(self, ws, account, _plus_path, useZmq = False, zmqServer = "tcp://localhost:9999"):

        self.ee = EventEngine(account)         # 创建事件驱动引擎

        self.userid = str(account['userid'])
        self.password = str(account['password'])
        self.brokerid = str(account['brokerid'])
        self.mdaddress = str(account['mdfront'])
        self.tdaddress = str(account['tdfront'])

        self.pluspath = _plus_path
        self.symbol = None
        self.socket = None
        self.websocket = ws             # websocket list to send msg

        if useZmq:
            context = zmq.Context()
            socket = context.socket(zmq.REQ)
            socket.connect(zmqServer)
            self.socket = socket

        self.ee.start()                 # 启动事件驱动引擎
        self.som = {}

        self.lastError = 0
        self.lastTodo = 0

        # 循环查询持仓和账户相关
        self.countGet = 0               # 查询延时计数
        self.lastGet = 'Account'        # 上次查询的性质
        self.ee.register(EVENT_TDLOGIN, self.initGet)  # 登录成功后开始初始化查询

        self.__timer = time()+3
        
        # 合约储存相关
        self.dictInstrument = {}        # 字典（保存合约查询数据）
        self.dictProduct = {}        # 字典（保存合约查询数据）
        self.dictExchange= {}
        self.volInstrument = {}
        self.subInstrument = set()
        self.subedInst = set()
        
        self.price = {} #   存储报价，分品种

        self.todo = 0

        self.ee.register(EVENT_ERROR,       self.get_error)
        self.ee.register(EVENT_INSTRUMENT,  self.insertInstrument)
        self.ee.register(EVENT_TIMER,       self.getAccountPosition)
        self.ee.register(EVENT_TRADE,       self.get_trade)
        self.ee.register(EVENT_ORDER,       self.get_order)
        self.ee.register(EVENT_TICK,        self.get_tick)
        self.ee.register(EVENT_POSITION,    self.get_position)

        self.ee.register(EVENT_TICK,        self.check_timer)
        self.ee.register(EVENT_ORDER,       self.check_timer)

        import eventType
        for k,v in eventType.__dict__.items():
            if 'EVENT_' in k and v[0]!='_':
                self.ee.register(v,self.websocket_send)

        self.md = DemoMdApi(self.ee, self.mdaddress, self.userid, self.password, self.brokerid,plus_path=_plus_path)    # 创建API接口
        self.td = DemoTdApi(self.ee, self.tdaddress, self.userid, self.password, self.brokerid,plus_path=_plus_path)

    def get_som(self,event):
        try:
            symbol = event.symbol
            if symbol in self.som:
                return self.som[symbol]
            else:
                one = SymbolOrdersManager(symbol,self.dictInstrument[symbol],self)
                self.som[symbol] = one
                return one
        except Exception,e:
            print("demoEngine.py MainEngine get_som not found event.symbol")
            print(event.dict_['data'])

    def check_timer(self,event):
        if time()>=self.__timer:
            self.__timer = time()+1
            event = Event(type_=EVENT_TIMER)
            self.ee.put(event)
    def set_ws(self,ws):
        self.websocket = ws
    def websocket_send(self,event):
        try:
            _data = json.dumps(event.dict_,ensure_ascii=False)
            for _ws in self.websocket:
                try:
                    _ws.send(_data)
                except Exception,e:
                    print(_data,e)
        except Exception,e:
            print(event.dict_,e)
    def get_error(self,event):
        print(event.dict_['log'])
        print(event.dict_['ErrorID'])
        self.lastError = event.dict_['ErrorID']
    def get_order(self,event):
        som = self.get_som(event)
        som.onorder(event)
    def get_trade(self,event):
        som = self.get_som(event)
        som.ontrade(event)
    def get_position(self,event):
        som = self.get_som(event)
        som.onposi(event)
    def get_tick(self,event):
        som = self.get_som(event)
        som.ontick(event)
    def zmq_heart(self):
        if self.socket:
            self.socket.send(bytes(json.dumps({"act":"ping"})))
            try:
                _msg = self.socket.recv()
                if _msg != "pong":print("zmq timeout")
            except Exception,e:
                print("zmq_heart error",e)
        else:
            print("no zmq")
    #----------------------------------------------------------------------
    def login(self):
        """登陆"""
        print("me.login")
        self.td.login()
        self.md.login()
    
    #----------------------------------------------------------------------
    def subscribe(self, instrumentid, exchangeid):
        """订阅合约"""
        if instrumentid not in self.subedInst:
            self.md.subscribe(str(instrumentid), str(exchangeid))
            self.subedInst.add(instrumentid)

    def sub_instrument(self,inst_id):
        if inst_id in self.dictInstrument:
            exch_id = self.dictInstrument[inst_id]['ExchangeID']
            self.subscribe(inst_id,exch_id)
            self.subInstrument.add(inst_id)
            self.symbol = str(inst_id)
            self.exchangeid = str(exch_id)
            event = Event(type_=EVENT_LOG)
            log = u'订阅合约: %s'%inst_id
            event.dict_['log'] = log
            self.ee.put(event)
        elif '_' in inst_id:
            _productID,_str = inst_id.split('_')
            _all = self.dictProduct.get(_productID,{})
            if _str == 'master' and _all:
                _minDate = 100000000
                _minID = ''
                for k,v in _all.items():
                    _id,_date = v
                    if _date < _minDate:
                        _minDate = _date
                        _minID = k
                exch_id = self.dictInstrument[_minID]['ExchangeID']
                self.subscribe(_minID,exch_id)
                self.symbol = str(_minID)
                self.exchangeid = str(exch_id)
                self.subInstrument.add(_minID)
                event = Event(type_=EVENT_LOG)
                log = u'订阅(主力)合约: %s'%_minID
                event.dict_['log'] = log
                self.ee.put(event)
        self.saveInstrument()

    #----------------------------------------------------------------------
    def getAccount(self):
        """查询账户"""
        self.td.getAccount()
        
    #----------------------------------------------------------------------
    def getInvestor(self):
        """查询投资者"""
        self.td.getInvestor()
        
    #----------------------------------------------------------------------
    def getPosition(self):
        """查询持仓"""
        self.td.getPosition()
    
    #----------------------------------------------------------------------
    def sendOrder(self, instrumentid, exchangeid, price, pricetype, volume, direction, offset):
        """发单"""
        self.td.sendOrder(instrumentid, exchangeid, price, pricetype, volume, direction, offset)
        
    #----------------------------------------------------------------------
    def cancelOrder(self, instrumentid, exchangeid, orderref, frontid, sessionid):
        """撤单"""
        self.td.cancelOrder(instrumentid, exchangeid, orderref, frontid, sessionid)
        
    #----------------------------------------------------------------------
    def getAccountPosition(self, event):
        """循环查询账户和持仓"""
        self.countGet = self.countGet + 1
        
        # 每1秒发一次查询
        if self.countGet > 0:
            if self.countGet>2:
                self.countGet = 0
                if self.lastGet == 'Account':
                    self.lastGet = 'Position'
                    self.getPosition()
                else:
                    self.lastGet = 'Account'
                    self.getAccount()
        else:
            self.getPosition()
    #----------------------------------------------------------------------
    def initGet(self, event):
        """在交易服务器登录成功后，开始初始化查询"""
        # 打开设定文件setting.vn
        self.getInstrument()
#        _exchangeid = self.dictInstrument[self.symbol]['ExchangeID']
        for _inst in list(self.subInstrument):
            self.sub_instrument(_inst)
    #----------------------------------------------------------------------
    def getInstrument(self):
        """获取合约"""

        event = Event(type_=EVENT_LOG)
        log = u'获取合约...'
        event.dict_['log'] = log
        self.ee.put(event)
        f = shelve.open(self.pluspath+'instrument')
        if f.get('date','')==date.today() and f.get('instrument',{}) and f.get('product',{}) and f.get('exchange',{}):
            self.dictProduct = f['product']
            self.dictInstrument = f['instrument']
            self.dictExchange = f['exchange']
            self.volInstrument = f.get('volinstrument',{})
            self.subInstrument = f.get('subinstrument',set())

            self.product_print()

            event = Event(type_=EVENT_PRODUCT)
            event.dict_['data'] = self.dictProduct
            self.ee.put(event)

            event = Event(type_=EVENT_LOG)
            log = u'得到本地合约!'
            event.dict_['log'] = log
            self.ee.put(event)
            self.getPosition()
        else:
            event = Event(type_=EVENT_LOG)
            log = u'查询合约信息...'
            event.dict_['log'] = log
            self.ee.put(event)
            self.td.getInstrument()
        f.close()
    def product_print(self):
        print("self.dictExchange ",self.dictExchange.keys())
        return(0)
        for k,v in self.dictProduct.items():
            print(k)
            for _inst,_data in v.items():
                print("  "+_inst+" : "+self.dictInstrument[_inst]['InstrumentName'])
                data = self.dictInstrument[_inst]
        print data
    def insertInstrument(self, event):
        """插入合约对象"""
        data = event.dict_['data']
        last = event.dict_['last']

        if data['ProductID'] not in self.dictProduct:
            self.dictProduct[data['ProductID']] = {}
        if data['ExchangeID'] not in self.dictExchange:
            self.dictExchange[data['ExchangeID']] = {}
        if data['ProductID'] not in self.dictExchange[data['ExchangeID']]:
            self.dictExchange[data['ExchangeID']][data['ProductID']] = {}
        if data['ProductID'] in data['InstrumentID'] and data['IsTrading']==1:
            self.dictExchange[data['ExchangeID']][data['ProductID']][data['InstrumentID']] = 1
            self.dictProduct[data['ProductID']][data['InstrumentID']] = (data['InstrumentName'],int(data['ExpireDate']))
            self.dictInstrument[data['InstrumentID']] = data

        # 合约对象查询完成后，查询投资者信息并开始循环查询
        if last:
            # 将查询完成的合约信息保存到本地文件，今日登录可直接使用不再查询
            self.saveInstrument()

            self.product_print()

            event = Event(type_=EVENT_LOG)
            log = u'合约信息查询完成!'
            event.dict_['log'] = log
            self.ee.put(event)            

            event1 = Event(type_=EVENT_PRODUCT)
            event1.dict_['data'] = self.dictProduct
            self.ee.put(event1)

            self.getPosition()

    #----------------------------------------------------------------------
    def selectInstrument(self, instrumentid):
        """获取合约信息对象"""
        try:
            instrument = self.dictInstrument[instrumentid]
        except KeyError:
            instrument = None
        return instrument
    
    #----------------------------------------------------------------------
    def exitEvent(self,e):
        self = None
    def exit(self):
        """退出"""
        # 销毁API对象
        self.td = None
        self.md = None
        
        # 停止事件驱动引擎
        self.ee.stop()

    def __del__(self):
        self.exit()
    #----------------------------------------------------------------------
    def saveInstrument(self):
        """保存合约属性数据"""
        f = shelve.open(self.pluspath+'instrument')
        f['instrument'] = self.dictInstrument
        f['product'] = self.dictProduct
        f['exchange'] = self.dictExchange
        f['volinstrument'] = self.volInstrument
        f['subinstrument'] = self.subInstrument
        f['date'] = date.today()
        f.close()
