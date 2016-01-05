from urllib2 import urlopen
import json

def tcpfunc(_dict,_som):
    _som.me.socket.send(bytes(json.dumps(_dict)))
    return int(_som.me.socket.recv())

def httpfunc(_dict,_som):
    _url = _som.me.coreServer
    _url += '/tick/%(account)s/%(eq).2f/%(price).2f/%(symbol)s/%(exchange)s/%(act)s/'%_dict
    try:
        _q = urlopen(_url,timeout=1000)
        return int(_q.readline())
    except:
        return 0

def passit(a,b):return 0

