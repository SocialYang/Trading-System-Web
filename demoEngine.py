# encoding: UTF-8

"""
该文件中包含的是交易平台的中间层，
将API和事件引擎包装到一个主引擎类中，便于管理。

当客户想采用服务器-客户机模式，实现交易功能放在托管机房，
而图形控制功能在本地电脑时，该主引擎负责实现远程通讯。
"""
#import sys
from datetime import date
from time import sleep,time
from copy import copy
import shelve
import json
import zmq

#from PyQt4 import QtCore

from demoApi import *
from eventEngine import EventEngine


########################################################################
class MainEngine:
    """主引擎，负责对API的调度"""

    #----------------------------------------------------------------------
    def __init__(self, ws, account, _plus_path, justCopySignal=False, useZmq = False, zmqServer = "tcp://localhost:9999"):
        """Constructor
        :type self: object
        """
        self.ee = EventEngine(account)         # 创建事件驱动引擎
        self.justCopySignal = justCopySignal

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
        self.havedposi = {}

        self.position = {}
        self._position = {}
        self.todayposition = {}
        self._todayposition = {}
        self.posicheck = set()

        self.lastError = 0
        self.lastTodo = 0

        self.__orders = {}
        self.__retry = 0
        self.__maxRetry = 5
        # 循环查询持仓和账户相关
        self.countGet = 0               # 查询延时计数
        self.lastGet = 'Account'        # 上次查询的性质
        self.ee.register(EVENT_TDLOGIN, self.initGet)  # 登录成功后开始初始化查询

        self.__timer = time()+10
        
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
#        self.ee.register(EVENT_TRADE,       self.get_trade)
        self.ee.register(EVENT_ORDER,       self.get_order)
        self.ee.register(EVENT_TICK,        self.get_tick)
        self.ee.register(EVENT_POSITION,    self.get_position)

        import eventType
        for k,v in eventType.__dict__.items():
            if 'EVENT_' in k and v[0]!='_':
                self.ee.register(v,self.websocket_send)

        self.md = DemoMdApi(self.ee, self.mdaddress, self.userid, self.password, self.brokerid,plus_path=_plus_path)    # 创建API接口
        self.td = DemoTdApi(self.ee, self.tdaddress, self.userid, self.password, self.brokerid,plus_path=_plus_path)

    def check_timer(self):
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
        self.check_timer()
        _data = event.dict_['data']
        if _data['OrderStatus'] == '5':
            self.__retry += 1
            if int(_data['OrderRef']) in self.__orders:
                _saved = self.__orders.pop(int(_data['OrderRef']))
            else:
                return 0
            if self.__retry>=self.__maxRetry:
                self.__retry = 0
                return 0
            event = Event(type_=EVENT_LOG)
            log = u'未成交已撤单，补单'
            event.dict_['log'] = log
            self.ee.put(event)
            if _saved[5] == defineDict["THOST_FTDC_D_Buy"]:
                _kr = 1
            elif _saved[5] == defineDict["THOST_FTDC_D_Sell"]:
                _kr = -1
            else:
                _kr = 0
            symbol = _saved[0]
            if _kr>0:
                price = float(_saved[2])+self.dictInstrument[symbol]['PriceTick']
            else:
                price = float(_saved[2])-self.dictInstrument[symbol]['PriceTick']
            _ref = self.td.sendOrder(_saved[0],_saved[1],price,_saved[3],_saved[4],_saved[5],_saved[6])
            self.__orders[_ref] = (_saved[0],_saved[1],price,_saved[3],_saved[4],_saved[5],_saved[6])
        elif _data['OrderStatus'] == '2':
            self.__retry += 1
            if int(_data['OrderRef']) in self.__orders:
                _saved = self.__orders.pop(int(_data['OrderRef']))
            else:
                return 0
            if self.__retry>=self.__maxRetry:
                self.__retry = 0
                return 0
            event = Event(type_=EVENT_LOG)
            log = u'部分成交，其余已撤单，补单'
            event.dict_['log'] = log
            self.ee.put(event)
            if _saved[5] == defineDict["THOST_FTDC_D_Buy"]:
                _kr = 1
            elif _saved[5] == defineDict["THOST_FTDC_D_Sell"]:
                _kr = -1
            else:
                _kr = 0
            symbol = _saved[0]
            if _kr>0:
                price = float(_saved[2])+self.dictInstrument[symbol]['PriceTick']
            else:
                price = float(_saved[2])-self.dictInstrument[symbol]['PriceTick']
            _todo = _saved[4]-_data['VolumeTraded']
            _ref = self.td.sendOrder(_saved[0],_saved[1],price,_saved[3],_todo,_saved[5],_saved[6])
            self.__orders[_ref] = (_saved[0],_saved[1],price,_saved[3],_todo,_saved[5],_saved[6])
        elif _data['OrderStatus'] == '0':
            event = Event(type_=EVENT_LOG)
            log = u'全部成交'
            event.dict_['log'] = log
            self.ee.put(event)
            if int(_data['OrderRef']) in self.__orders:
                _saved = self.__orders.pop(int(_data['OrderRef']))
                return 0
            self.__retry = 0
    def get_trade(self,event):
        self.check_timer()
        _data = event.dict_['data']
    def get_position(self,event):
        _data = event.dict_['data']
        print(_data['InstrumentID'],_data['PosiDirection'],_data['PositionDate'],_data['Position'])

        self.havedposi[_data['InstrumentID']] = 1

        _ord = {}
        for k,v in self.__orders.items():
            if _data['InstrumentID']==v[0]:
                pass
            else:
                _ord[k] = v
        self.__orders = _ord

        _key = (_data['InstrumentID'],_data['PosiDirection'],_data['PositionDate'])
        if _key in self.posicheck:

            self.position = copy(self._position)
            self.todayposition = copy(self._todayposition)
            self._position = {}
            self._todayposition = {}

            print("today",self.todayposition)
            print("old",self.position)
            print("="*20)

            _out = {}
            for k,v in self.position.items():
                _out[k[:2]] = {}
                _out[k[:2]]['YdPosition'] = v
                _out[k[:2]]['InstrumentID'] = k[0]
                _out[k[:2]]['PosiDirection'] = k[1]
            for k,v in self.todayposition.items():
                if k[:2] in _out:
                    _out[k[:2]]['TodayPosition'] = v
                    _out[k[:2]]['Position'] = v+_out[k[:2]]['YdPosition']
                else:
                    _out[k[:2]] = {}
                    _out[k[:2]]['InstrumentID'] = k[0]
                    _out[k[:2]]['PosiDirection'] = k[1]
                    _out[k[:2]]['YdPosition'] = 0
                    _out[k[:2]]['TodayPosition'] = v
                    _out[k[:2]]['Position'] = v

            for k,v in _out.items():
                event = Event(type_=EVENT_POSIALL)
                event.dict_['data'] = v
                self.ee.put(event)

            self.posicheck.clear()
            self.posicheck.add(_key)

        else:
            self.posicheck.add(_key)

        if int(_data['PositionDate'])==2:
            self._position[(_data['InstrumentID'],_data['PosiDirection'])] = _data['Position']
            if _data['InstrumentID'] not in self.subInstrument and _data['Position']>0:
                if _data['InstrumentID'] not in self.subedInst:
                    self.subscribe(_data['InstrumentID'],'')
                elif _data['InstrumentID'] in self.price and _data['InstrumentID'] in self.dictInstrument:
                    self.closePosition(str(_data['InstrumentID']),str(int(_data['PosiDirection'])-2),_data['Position'])
                    self._position.pop((_data['InstrumentID'],_data['PosiDirection']))
        elif int(_data['PositionDate'])==1:
            self._todayposition[(_data['InstrumentID'],_data['PosiDirection'])] = _data['Position']
            if _data['InstrumentID'] not in self.subInstrument and _data['Position']>0:
                if _data['InstrumentID'] not in self.subedInst:
                    self.subscribe(_data['InstrumentID'],'')
                elif _data['InstrumentID'] in self.price and _data['InstrumentID'] in self.dictInstrument:
                    self.closeTodayPosition(str(_data['InstrumentID']),str(int(_data['PosiDirection'])-2),_data['Position'])
                    self._todayposition.pop((_data['InstrumentID'],_data['PosiDirection']))
        else:
            print(u'未知持仓日期')
            print(_data)

    def openPosition(self,symbol,tr,volume):
        event = Event(type_=EVENT_LOG)
        log = u'开仓[%s] %d %d'%(symbol,tr,volume)
        event.dict_['log'] = log
        self.ee.put(event)
        self.__retry = 0
        self.countGet = -5
        offset = defineDict['THOST_FTDC_OF_Open']
        pricetype = defineDict['THOST_FTDC_OPT_LimitPrice']
        if tr>0:
            price = self.price[symbol]['ask']+self.dictInstrument[symbol]['PriceTick']*2.0
            direction = defineDict["THOST_FTDC_D_Buy"]
        else:   
            price = self.price[symbol]['bid']-self.dictInstrument[symbol]['PriceTick']*2.0
            direction = defineDict["THOST_FTDC_D_Sell"]
        _instrumentid = self.dictInstrument[symbol]
        exchangeid = _instrumentid["ExchangeID"]
        _ref = self.td.sendOrder(symbol,exchangeid,price,pricetype,volume,direction,offset)
        self.__orders[_ref] = (symbol,exchangeid,price,pricetype,volume,direction,offset)
    def closePosition(self,symbol,tr,volume):
        event = Event(type_=EVENT_LOG)
        log = u'平仓[%s] %d %d'%(symbol,tr,volume)
        event.dict_['log'] = log
        self.ee.put(event)
        self.__retry = 0
        self.countGet = -5
        offset = defineDict['THOST_FTDC_OF_Close']
        pricetype = defineDict['THOST_FTDC_OPT_LimitPrice']
        if tr<0:
            price = self.price[symbol]['ask']+self.dictInstrument[symbol]['PriceTick']*2.0
            direction = defineDict["THOST_FTDC_D_Buy"]
        else:   
            price = self.price[symbol]['bid']-self.dictInstrument[symbol]['PriceTick']*2.0
            direction = defineDict["THOST_FTDC_D_Sell"]
        _instrumentid = self.dictInstrument[symbol]
        exchangeid = _instrumentid["ExchangeID"]
        _ref = self.td.sendOrder(symbol,exchangeid,price,pricetype,volume,direction,offset)
        self.__orders[_ref] = (symbol,exchangeid,price,pricetype,volume,direction,offset)
    def closeTodayPosition(self,symbol,tr,volume):
        event = Event(type_=EVENT_LOG)
        log = u'平今仓[%s] %d %d'%(symbol,tr,volume)
        event.dict_['log'] = log
        self.ee.put(event)
        self.__retry = 0
        self.countGet = -5
        offset = defineDict['THOST_FTDC_OF_CloseToday']
        pricetype = defineDict['THOST_FTDC_OPT_LimitPrice']
        if tr<0:
            price = self.price[symbol]['ask']+self.dictInstrument[symbol]['PriceTick']*2.0
            direction = defineDict["THOST_FTDC_D_Buy"]
        else:   
            price = self.price[symbol]['bid']-self.dictInstrument[symbol]['PriceTick']*2.0
            direction = defineDict["THOST_FTDC_D_Sell"]
        _instrumentid = self.dictInstrument[symbol]
        exchangeid = _instrumentid["ExchangeID"]
        _ref = self.td.sendOrder(symbol,exchangeid,price,pricetype,volume,direction,offset)
        self.__orders[_ref] = (symbol,exchangeid,price,pricetype,volume,direction,offset)
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
    def get_tick(self,event):
        self.check_timer()
        _data = event.dict_['data']
        _ask = _data['AskPrice1']
        _bid = _data['BidPrice1']
        _symbol = _data['InstrumentID']
        if _symbol in self.dictInstrument:
            _exchange =  self.dictInstrument[_symbol]["ExchangeID"]
        else:
            _exchange = ''
        _price = (_ask+_bid)/2.0
        self.price[_symbol] = {"ask":_ask,"price":_price,"bid":_bid}
        if _symbol not in self.subInstrument:
            event = Event(type_=EVENT_LOG)
            log = u'非订阅合约[%s]'%_symbol
            print(self.subInstrument)
            event.dict_['log'] = log
            self.ee.put(event)
            return #   非订阅合约
        if self.socket:
            if self.justCopySignal:
                self.socket.send(bytes(json.dumps({"act":"getresult"})))
            else:
                self.socket.send(bytes(json.dumps({"data":_price})))
        else:
            return
        _bk = int(self.socket.recv())
        if _symbol[:2] in ['IF','IH','IC'] and _data['UpdateTime'][:4]=='15:1':
            _bk = 0
        self.todo = _bk
        if self.lastError in [31,50]:
            if self.lastTodo == self.todo:
                return
            else:
                self.lastTodo = self.todo
        if self.__orders:
            print(self.__orders)
        elif self.havedposi.get(_symbol,0)>0:
            _long = (_symbol,defineDict["THOST_FTDC_PD_Long"])
            _short = (_symbol,defineDict["THOST_FTDC_PD_Short"])
            if self.todo==0:
                if self.position.get(_long,0)>0:
                    self.closePosition(_symbol,1,self.position[_long])
                    self.havedposi[_symbol] = 0
                if self.todayposition.get(_long,0)>0:
                    self.closeTodayPosition(_symbol,1,self.todayposition[_long])
                    self.havedposi[_symbol] = 0
                    
                if self.position.get(_short,0)>0:
                    self.closePosition(_symbol,-1,self.position[_short])
                    self.havedposi[_symbol] = 0
                if self.todayposition.get(_short,0)>0:
                    self.closeTodayPosition(_symbol,-1,self.todayposition[_short])
                    self.havedposi[_symbol] = 0
                    
            def do_it(_todo,_pass,_reverse,d_pass,d_reverse):
                if self.position.get(_reverse,0)>0:
                    self.closePosition(_symbol,d_reverse,self.position[_reverse])
                    self.havedposi[_symbol] = 0
                if self.todayposition.get(_reverse,0)>0:
                    self.closeTodayPosition(_symbol,d_reverse,self.todayposition[_reverse])
                    self.havedposi[_symbol] = 0
                _haved = self.position.get(_pass,0)+self.todayposition.get(_pass,0)
                if _todo>_haved:
                    self.openPosition(_symbol,d_pass,_todo-_haved)
                    self.havedposi[_symbol] = 0
                if _todo<_haved:
                    if self.position.get(_pass,0)>0:
                        self.closePosition(_symbol,d_pass,min(self.position[_pass],_haved-_todo))
                        self.havedposi[_symbol] = 0
                        if self.position[_pass]<_haved-_todo:
                            self.closeTodayPosition(_symbol,d_pass,_haved-_todo-self.position[_pass])
                            self.havedposi[_symbol] = 0
                elif self.todayposition.get(_pass,0)>0:
                        self.closeTodayPosition(_symbol,d_pass,_haved-_todo)
                        self.havedposi[_symbol] = 0

            if self.todo>0:
                _todo = self.todo
                _pass = _long
                _reverse = _short
                d_pass = 1
                d_reverse = -1

                do_it(_todo,_pass,_reverse,d_pass,d_reverse)
                
            if self.todo<0:
                _todo = abs(self.todo)
                _pass = _short
                _reverse = _long
                d_pass = -1
                d_reverse = 1

                do_it(_todo,_pass,_reverse,d_pass,d_reverse)
                
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
