import time,datetime
#from svgcandle import *
from math import ceil
from mongo_settings import *

class Stage:
    def get_result(self):

        c = self.cache
        
        pos = self.todo[0]        
        _Max = 20
        _result = list(self.db[pos].find({},sort=[('_id',desc)],limit=_Max))
        
        ma10 = sum([one['c'] for one in _result[:10]])/10.0
        ma20 = sum([one['c'] for one in _result[:20]])/20.0

        for i in self.todo:
            c[i][0]['ma10'] = ma10
            c[i][0]['ma20'] = ma20
            self.cache[i][0] = c[i][0]
            self.save(i,c[i][0])
            
        if ma10>ma20:
            return 1
        else:
            return -1
#=====================================================================
    def __init__(self,symbol,time=None,plus=""):
        self.plus = plus
        self.db = {}
        self.data={}
        self.symbol = symbol+plus
        self.result = {}
        self.todo = [3600]
        if time:
            self.time = time
        else:
            self.time = time.time()
        for i in self.todo:
            self.db[i] = conn[self.symbol][str(i)]

    def price(self,price):
        for i in self.todo:
            self.new_price(price,i)
            
    def new_price(self,price,pos):
        _result = list(self.db[pos].find({},sort=[('_id',desc)],limit=1))

        if len(_result)>0:
            now = _result[0]
            now['c'] = price
            now['h'] = max(now['c'],now['h'])
            now['l'] = min(now['c'],now['l'])
            now['time'] = self.time
            now = self.check_k_hour(now,pos)
        else:
            last = None
            now = {'_id':0,'o':price,'h':price,'l':price,'c':price,'begin':self.time}
            self.save(pos,now)
    def check_k_hour(self,now,pos):
        if int(now.get('begin',-1)/pos)!=int(now.get('time',-1)/pos):
            p = now['c']
            new = {'o':p,'h':p,'l':p,'c':p,'do':0,'begin':self.time}
            new['_id'] = int(self.time/pos)
            self.save(pos,now)
            self.save(pos,new)
            return new
        else:
            self.save(pos,now)
            return now

    def data_out(self,pos):
        _result = self.db[pos].find({},sort=[('_id',desc)],limit=2)
        return jsondump(list(_result))
#=====================================================================
    def save(self,Pos,Dict):
        self.db[Pos].save(Dict)
#=====================================================================
'''
    def get_image(self,pos,lens,group,offset=0):
        data = self.db[int(pos)]
        result = list(data.find(sort=[('_id',desc)],limit=int(lens),skip=int(offset)*int(lens)))
        _l = self.state.get('his',['none'])[::-1]
        out = SVG(group,result[::-1],_l,data).to_html()
        return out
    def only_image(self,pos,lens,group,offset=0):
        data = self.db[int(pos)]
        result = list(data.find(sort=[('_id',desc)],limit=int(lens),skip=int(offset)*int(lens)))
        out = SVG(group,result[::-1],[self.symbol+" "+str(datetime.datetime.now())[:19]],data).to_html()
        return out'''
############################################################################################################
'''
#        end
'''
############################################################################################################
