# encoding: UTF-8
from datetime import date,datetime
from time import time
from rule import Product_Time_Rule
import zmq
from string import lowercase as _chars
from string import uppercase as _CHARS

_YDPOSITIONDATE_ = '2'
_TODAYPOSITIONDATE_ = '1'

from ctpApi import *
from eventEngine import EventEngine
from threading import Lock

class SymbolOrdersManager:
    def __init__(self,symbol,data,me):
        self.symbol = symbol
        self.data = data
        self.exchange = data['ExchangeID']
        self.productid = data['ProductID']
        self.me = me
        self.__lock = Lock()
        self.__maxRetry = 5
        self.__status = {}
        self.__stlist = set()
        self.__orders = {}
        self.__hold = 0
        self.__last = 0
        self.__timecheck = 0
        self.__timepass = 0
        self.__timerule = Product_Time_Rule.get(self.productid,[lambda x:x<0])#默认不交易
        self.__price = {}
        print("Symbol:",self.data)
    def openPosition(self,tr,volume):
        print(tr,volume)
        if volume<=0:return
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
        self.__orders[_ref] = (self.symbol,exchangeid,price,pricetype,volume,direction,offset,0,time())
    def closePosition(self,tr,volume):
        print(tr,volume)
        if volume<=0:return
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
        self.__orders[_ref] = (self.symbol,exchangeid,price,pricetype,volume,direction,offset,0,time())
    def closeTodayPosition(self,tr,volume):
        print(tr,volume)
        if volume<=0:return
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
        self.__orders[_ref] = (self.symbol,exchangeid,price,pricetype,volume,direction,offset,0,time())
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
            self.__orders[_ref] = (_saved[0],_saved[1],price,_saved[3],_saved[4],_saved[5],_saved[6],_saved[7]+1,_saved[8])
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
            self.__orders[_ref] = (_saved[0],_saved[1],price,_saved[3],_todo,_saved[5],_saved[6],_saved[7]+1,_saved[8])
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
                if (self.symbol,self.exchange) not in self.me.subInstrument:
                    self.__hold = 0
                else:
                    self.me.socket.send(bytes(json.dumps({"price":self.__price['price'],"symbol":self.me.master.get(self.symbol,self.symbol),"act":"result"})))
                    self.__hold = int(self.me.socket.recv())
                    if self.__hold!=0:self.__last = self.__hold
            else:
                return
            if int(self.me.lastError) in [31,50]:
                self.__orders = {}
                self.me.lastError = 0
            for k,v in self.__orders.items():
                if time()-v[8]>1:
                    self.__orders.pop(k)
            if len(self.__orders)>0:
                print(self.symbol,self.__orders)
            else:
                if time()>self.__timecheck:
                    self.__timecheck = int(time()/60)*60+60
                    _now = datetime.now()
                    _time = _now.hour*100+_now.minute
                    self.__timepass = filter([one(_time) for one in self.__timerule]).count(True)
                if self.__timepass>0:pass
                else:return
                _long       =   defineDict["THOST_FTDC_PD_Long"]
                _short      =   defineDict["THOST_FTDC_PD_Short"]
                long_st     =   self.__status.get(_long,{})
                short_st    =   self.__status.get(_short,{})

#                print(self.symbol,self.__status,"BEFORE",self.__hold)

                def do_it(_todo,_pass,_reverse,d_pass,d_reverse):
                    if self.__status.get(_reverse,{}).get(_YDPOSITIONDATE_,0)>0:
                        self.closePosition(d_reverse,self.__status[_reverse][_YDPOSITIONDATE_])
                    if self.__status.get(_reverse,{}).get(_TODAYPOSITIONDATE_,0)>0:
                        if self.productid in ['IF','IH','IC']:
                            self.closeTodayPosition(d_reverse,self.__status[_reverse][_TODAYPOSITIONDATE_])
                        else:
                            self.closePosition(d_reverse,self.__status[_reverse][_TODAYPOSITIONDATE_])

                    self.__status[_reverse] = {}

                    _old = self.__status.get(_pass,{})
                    _old_old = _old.get(_YDPOSITIONDATE_,0)
                    _old_today = _old.get(_TODAYPOSITIONDATE_,0)
                    _haved = sum(_old.values())

                    if _todo>_haved:
                        self.openPosition(d_pass,_todo-_haved)
                        _old[_TODAYPOSITIONDATE_] = _old_today+(_todo-_haved)
                    elif _todo<_haved:
                        if _todo-_haved > _old_old:
                            # 昨仓全平 今仓平一部分
                            self.closePosition(_pass,_old_old)
                            _old[_YDPOSITIONDATE_] = 0
                            if self.productid in ['IF','IH','IC']:
                                self.closeTodayPosition(_pass,_todo-_haved-_old_old)
                            else:
                                self.closePosition(_pass,_todo-_haved-_old_old)
                            _old[_TODAYPOSITIONDATE_] = _old_today - (_todo-_haved-_old_old)
                        elif _todo-_haved == _old_old:
                            # 昨仓全平
                            self.closePosition(_pass,_old_old)
                            _old[_YDPOSITIONDATE_] = 0
                        else:
                            # 昨仓平一部分
                            self.closePosition(_pass,_todo-_haved)
                            _old[_YDPOSITIONDATE_] = _old_old - (_todo-_haved)

                    self.__status[_pass] = _old

                if self.__hold==0:
                    if long_st.get(_YDPOSITIONDATE_,0)>0:
                        self.closePosition(1,long_st[_YDPOSITIONDATE_])
                    if long_st.get(_TODAYPOSITIONDATE_,0)>0:
                        if self.productid in ['IF','IH','IC']:
                            self.closeTodayPosition(1,long_st[_TODAYPOSITIONDATE_])
                        else:
                            self.closePosition(1,long_st[_TODAYPOSITIONDATE_])
                    if short_st.get(_YDPOSITIONDATE_,0)>0:
                        self.closePosition(-1,short_st[_YDPOSITIONDATE_])
                    if short_st.get(_TODAYPOSITIONDATE_,0)>0:
                        if self.productid in ['IF','IH','IC']:
                            self.closeTodayPosition(-1,short_st[_TODAYPOSITIONDATE_])
                        else:
                            self.closePosition(-1,short_st[_TODAYPOSITIONDATE_])
                    self.__status = {}
                    if self.__last != self.__hold:
                        self.__last = self.__hold
                        for _key in ['2','3']:
                            _dict = {}
                            _dict['InstrumentID'] = self.symbol
                            _dict['PosiDirection'] = _key
                            _dict['TodayPosition'] = 0
                            _dict['YdPosition'] = 0
                            _dict['Position'] = 0
                            event = Event(type_=EVENT_POSIALL)
                            event.dict_['data'] = _dict
                            self.me.ee.put(event)
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

#                print(self.symbol,self.__status,"AFTER",self.__hold)
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
                for k,v in self.__status.items():
                    _dict = {}
                    _dict['InstrumentID'] = self.symbol
                    _dict['PosiDirection'] = k
                    _dict['TodayPosition'] = v.get(_TODAYPOSITIONDATE_,0)
                    _dict['YdPosition'] = v.get(_YDPOSITIONDATE_,0)
                    _dict['Position'] = _dict['TodayPosition']+_dict['YdPosition']
                    event = Event(type_=EVENT_POSIALL)
                    event.dict_['data'] = _dict
                    self.me.ee.put(event)
                self.__stlist = set()
                self.__stlist.add((_dir,_date))
            else:
                self.__stlist.add((_dir,_date))

        if (self.symbol,self.exchange) not in self.me.subedInstrument:
            self.me.subscribe(self.symbol, self.exchange)

########################################################################
class MainEngine:

    #----------------------------------------------------------------------
    def __init__(self, account, _plus_path, bg):

        self.ee = EventEngine(account)         # 创建事件驱动引擎
        self.bridge = bg
        self.userid = str(account['userid'])
        self.password = str(account['password'])
        self.brokerid = str(account['brokerid'])
        self.mdaddress = str(account['mdfront'])
        self.tdaddress = str(account['tdfront'])
        self.instrument = account['instrument'] #   sub list str
        self.pluspath = _plus_path

        self.dictInstrument = {}        # 字典（保存合约查询数据）
        self.dictProduct = {}        # 字典（保存合约查询数据）
        self.dictExchange= {}
        self.dictUpdate = None
        self.subInstrument = set()
        self.subedInstrument = set()
        self.master = {}    #   记录主力合约对应关系
        self.socket = None
        if int(account['usezmq'])>0:
            context = zmq.Context()
            socket = context.socket(zmq.REQ)
            socket.connect(str(account['zmqserver']))
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
        self.__readySubscribe = {}
        
        # 合约储存相关

        self.get_instrument()
        self.get_subscribe(self.instrument)
        self.ee.register(EVENT_MDLOGIN,     self.ready_subscribe)
        self.ee.register(EVENT_TDLOGIN,     self.ready_subscribe)
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

        self.md = ctpMdApi(self, self.mdaddress, self.userid, self.password, self.brokerid, plus_path=_plus_path)    # 创建API接口
        self.td = ctpTdApi(self, self.tdaddress, self.userid, self.password, self.brokerid, plus_path=_plus_path)
    def get_subscribe(self,_inst):
        _all = _inst.split('+')
        _today = date.today()
        _date = int("%d%d%d"%(_today.year,_today.month,_today.day))
        for one in _all:
            if '=' in one:
                _productid = one[:-1]
                if _productid in self.dictProduct:
                    _product = self.dictProduct[_productid]
                    _productlist = filter( lambda x:x[0]>_date , [ (v[-1],k) for k,v in _product.items()] )
                    _productlist.sort()
                    _instrumentid = _productlist[0][-1]
                    _exchangeid = self.dictInstrument.get(_instrumentid,{}).get("ExchangeID",'')
                    self.subInstrument.add((_instrumentid,_exchangeid))
                    self.master[_instrumentid] = one[:-1]
            else:
                _instrumentid = one
                _exchangeid = self.dictInstrument.get(_instrumentid,{}).get("ExchangeID",'')
                self.subInstrument.add((_instrumentid,_exchangeid))
    def ready_subscribe(self,event):
        self.__readySubscribe[event.type_] = 1
        if len(self.__readySubscribe) == 2:
            for one in self.subInstrument:
                if one[0] in self.master:
                    event = Event(type_=EVENT_LOG)
                    log = u'订阅主力合约:%s[%s]'%(one[0],self.master[one[0]])
                    event.dict_['log'] = log
                    self.ee.put(event)
                else:
                    event = Event(type_=EVENT_LOG)
                    log = u'订阅合约:%s'%one[0]
                    event.dict_['log'] = log
                    self.ee.put(event)
                self.subscribe(one[0],one[1])
    def get_instrument(self):
        _dict = self.bridge.get_instrument()
        self.dictInstrument = _dict.get('instrument',{})
        self.dictExchange = _dict.get('exchange',{})
        self.dictProduct = _dict.get('product',{})
        self.dictUpdate = _dict.get('day',None)
    def set_instrument(self):
        _dict = {}
        _dict['instrument'] = self.dictInstrument
        _dict['exchange'] = self.dictExchange
        _dict['product'] = self.dictProduct
        _dict['day'] = date.today()
        self.bridge.set_instrument(_dict)
    def get_som(self,event):
        try:
            symbol = event.dict_['data']['InstrumentID']
            if symbol:
                if symbol in self.som:
                    return self.som[symbol]
                else:
                    _data = None
                    if symbol in self.dictInstrument:
                        _data = self.dictInstrument[symbol]
                        event = Event(type_=EVENT_LOG)
                        log = u'初始化合约[%s]并填充其基本信息'%symbol
                        event.dict_['log'] = log
                        self.ee.put(event)
                    else:
                        _productid = filter(lambda x:x in _chars+_CHARS,symbol)
                        if _productid in self.dictProduct:
                            for _instrument in self.dictProduct[_productid].keys():
                                if _instrument in self.dictInstrument:
                                    _data = self.dictInstrument[_instrument]
                                    event = Event(type_=EVENT_LOG)
                                    log = u'注意:初始化合约[%s]但填充了<%s>的基本信息'%(symbol,_instrument)
                                    event.dict_['log'] = log
                                    self.ee.put(event)
                                    break
                    if _data:
                        one = SymbolOrdersManager(symbol,_data,self)
                        self.som[symbol] = one
                        return one
                    else:
                        event = Event(type_=EVENT_LOG)
                        log = u'警告:初始化合约[%s]失败，未发现其基本信息'%symbol
                        event.dict_['log'] = log
                        self.ee.put(event)
                        print("demoEngine.py MainEngine get_som not found Instrument Info")
                        return None
            else:
                return None
        except Exception,e:
            print("demoEngine.py MainEngine get_som ERROR",e)
            print(event.type_,event.dict_['data'])
    def check_timer(self,event):
        if time()>=self.__timer:
            self.__timer = time()+1
            event = Event(type_=EVENT_TIMER)
            self.ee.put(event)
    def set_ws(self,ws):
        self.websocket = ws
    def websocket_send(self,event):
        self.bridge.send_ws(event)
    def get_error(self,event):
        print(event.dict_['log'])
        print(event.dict_['ErrorID'])
        self.lastError = event.dict_['ErrorID']
    def get_order(self,event):
        som = self.get_som(event)
        if som:som.onorder(event)
    def get_trade(self,event):
        som = self.get_som(event)
        if som:som.ontrade(event)
    def get_position(self,event):
        som = self.get_som(event)
        if som:som.onposi(event)
    def get_tick(self,event):
        som = self.get_som(event)
        if som:som.ontick(event)
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
        self.md.subscribe(str(instrumentid), str(exchangeid))
        self.subedInstrument.add((instrumentid, exchangeid))
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
        self.getInstrument()
    #----------------------------------------------------------------------
    def getInstrument(self):
        """获取合约"""

        event = Event(type_=EVENT_LOG)
        log = u'获取合约...'
        event.dict_['log'] = log
        self.ee.put(event)

        if self.dictUpdate==date.today():

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
            self.dictUpdate = date.today()
            self.set_instrument()

            event = Event(type_=EVENT_LOG)
            log = u'合约查询完成!'
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
