#coding:utf-8

import time
import zmq
import json
from stage import Stage

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:9999")

def simpletest(_price):
	st = Stage("test")
	st.price(_price)
	return str(st.get_result())

def heart(_price):
	return "pong"

Funcs = {
	"ping":heart,
}

while True:
	try:
		_dict = json.loads(socket.recv())
		_func = Funcs.get(_dict.get("act","none"),simpletest)
		bk = _func(_dict.get("data",0.0))
	except:
		bk = 'zmq_err'
	finally:
		socket.send(bytes(bk))
