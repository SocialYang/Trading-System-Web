from log import logit
from dom import dictomongo as dom
from pymongo import Connection
from pymongo import ASCENDING as asc
from pymongo import DESCENDING as desc
from bson.json_util import loads as jsonload
from bson.json_util import dumps as jsondump
from myth import *
allstate = dom('states')
conn = Connection(host=mongo_server,port=27017,max_pool_size=10,network_timeout=5)
