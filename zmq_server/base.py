vsn = 'in.2015.12.28.0'
import time,datetime
from life import *
from svgcandle import *
from qqmail import alertmail
import thread
import acc

def clear_old(db,days):
    _time = time.time()-days*24*3600
    db.remove({'_time':{'$lt':_time}})

class Base:
    def __init__(self,exchange,symbol,dbConnection,dbState,plus=''):
        self.symbol = "k_%s_%s_%s"%(exchange,symbol,plus)
        self.raw = "raw_%s_%s_%s"%(exchange,symbol,plus)
        self.plus = plus
        self.db = {}
        self.todo = ['3600']
        self.raw = dbConnection[self.raw]['raw']
        for i in self.todo:self.db[i] = dbConnection[self.symbol][i]
        _a = allstate[self.symbol]
        if _a:
            self.state = _a[0]
        else:
            self.state = {}
        self.hour = None
        self.cache = {}
        self.money = 0.0
#=====================================================================
    def get_timeframe(self):
        return self.todo
    def get_result(self):
        c = self.cache
        s = self.state
        i = self.todo[0]

        if len(c[i])<2:return {}

        _Max = 20
        _result = list(self.db[i].find({},sort=[('_id',desc)],limit=_Max))

        ma10 = sum([one['c'] for one in _result[:10]])/10.0
        ma20 = sum([one['c'] for one in _result[:20]])/20.0

        for one in self.todo:
            c[one][0]['ma10'] = ma10
            c[one][0]['ma20'] = ma20
            self.cache[one][0] = c[one][0]
            self.save(one,c[one][0])

        if ma10>ma20:
            return {'result':1}
        else:
            return {'result':-1}

    def data_out(self,pos):
        _result = self.db[pos].find({'_do':1},sort=[('_id',desc)],limit=2)
        return jsondump(list(_result))
    def data_in(self,pos,_str):
        self.save(pos,jsonload(_str))
        print "save ok",pos
        return 'ok'
    def account_money(self,money):self.money = money
    def period_job(self):
        for one in self.todo:
            thread.start_new_thread(clear_old,(self.db[one],5))
        thread.start_new_thread(clear_old,(self.raw,30))
        thread.start_new_thread(alertmail,("Account:%s_Eq:%.0f_Point:%.1f"%(acc.account,self.money,self.state.get("base_p",0.0)),))
    def get_image(self,pos,lens,group,offset=0):
        result = list(self.db[pos].find(sort=[('_id',desc)],limit=int(lens),skip=int(offset)*int(lens)))
        _l = self.state.get('his',['none'])[::-1]
        out = SVG(group,result[::-1],_l).to_html()
        return out
    def only_image(self,pos,lens,group,offset=0):
        result = list(self.db[pos].find(sort=[('_id',desc)],limit=int(lens),skip=int(offset)*int(lens)))
        out = SVG(group,result[::-1],[str(datetime.datetime.now())]).to_html()
        return out
    def save(self,Pos,Dict):
        self.db[Pos].save(Dict)
    def check_base(self,pos,_todo,_last):
#        _todo,_last = fill_base(_todo,_last)
        _todo['_do'] = 1
        if _last:
            self.cache[pos] = [_todo,_last]
            self.save(pos,_last)
        else:
            self.cache[pos] = [_todo]
        self.save(pos,_todo)
#        self.state['length'] = get_length(c[i][0])
        return _todo
    def check_k_period(self,now,last,timeframe):
        _hour = int(self.timer/int(timeframe))
        if now.get('hour',0)!=_hour:
            p = now['c']
            new = {'o':p,'h':p,'l':p,'c':p,'_do':0,'_hour':_hour,'point':self.state.get('point',0)}
            new['_id'] = int(self.timer/3600)*1000000
            new['_cnt'] = 0
            now = self.check_base(timeframe,now,last)

            if self.plus!='':
                self.period_job()
            return (new,now)
        return (now,last)
    def check_k_len(self,now,last,pos):
        length = self.state.get('length',8)
        if now['h']-now['o']>length:
            high = now['h']
            now['h'] = now['o']+length
            now['c'] = now['o']+length

            new = {'o':now['c'],'h':high,'l':now['c'],'c':now['c'],'_do':0,'_hour':now['_hour'],'point':self.state.get('point',0)}
            new['_cnt'] = now.get('_cnt',0)+1
            new['_id'] = now['_id']+1

            self.check_len(pos)
            now = self.check_base(pos,now,last)
            return self.check_k_len(new,now,pos)
        elif now['o']-now['l']>length:
            low = now['l']
            now['l'] = now['o']-length
            now['c'] = now['o']-length

            new = {'o':now['c'],'h':now['c'],'l':low,'c':now['c'],'_do':0,'_hour':now['_hour'],'point':self.state.get('point',0)}
            new['_cnt'] = now.get('_cnt',0)+1
            new['_id'] = now['_id']+1
            self.check_len(pos)
            now = self.check_base(pos,now,last)
            return self.check_k_len(new,now,pos)
        else:
            return (now,last)
    def do_price(self,timeframe,price):
        _result = list(self.db[timeframe].find({'_do':1},sort=[('_id',desc)],limit=2))
        if len(_result)>0:
            now = _result[0]
            if len(_result)>1:
                last = _result[1]
            else:
                last = None
            now['c'] = price
            now['h'] = max(now['c'],now['h'])
            now['l'] = min(now['c'],now['l'])
            now['_time'] = self.timer
            now['_do'] = 0
#            now,last = self.check_k_len(now,last,timeframe)
            now,last = self.check_k_period(now,last,timeframe)
            self.check_base(timeframe,now,last)
        else:
            last = None
            now = {'_id':0,'_do':0,'o':price,'h':price,'l':price,'c':price,'_hour':0,'point':0}
            self.check_base(timeframe,now,last)
    def new_price(self,timer,price,realprice):
        self.timer = timer
        self.price = price
        self.realprice = realprice
        if self.plus == '':
            self.raw.save({"_time":timer,"point":price,"price":realprice})   #   save tick to raw
        for one in self.todo:
            self.do_price(one,price)
############################################################################################################
'''
#        end
'''
############################################################################################################
