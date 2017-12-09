# encoding: UTF-8

import hashlib
import zlib
import json
from time import sleep
from threading import Thread
from Queue import Queue, Empty
import requests
import urllib
import time
import hmac

API_URL = 'https://api.quoine.com'
API_VERSION = '2'
SIDE_BUY = 'buy'
SIDE_SELL = 'sell'

ORDER_TYPE_LIMIT = 'limit'
ORDER_TYPE_MARKET = 'market'

METHOD_GET_PRODUCTS = 'products'
METHOD_GET_ORDERBOOK = ''

########################################################################
class DataApi(object):
    """交易接口"""
    DEBUG = True

    #----------------------------------------------------------------------
    def __init__(self, access_key='', secret_key=''):
        """Constructor"""
        self.accessKey = access_key
        self.secretKey = secret_key

        self.active = False         # API工作状态
        self.reqID = 0              # 请求编号
        self.reqQueue = Queue()     # 请求队列
        self.reqThread = Thread(target=self.processQueue)   # 请求处理线程

    #----------------------------------------------------------------------
    def signature(self, params):
        """生成签名"""
        message = urllib.urlencode(params)
        m = hmac.new(bytes(self.secretKey.encode('utf-8')), message.encode('utf-8'), hashlib.sha256)
        sig = m.hexdigest()
        return sig

    #----------------------------------------------------------------------
    def processRequest(self, req):
        """处理请求"""
        method = req['method']
        params = req['params']
        url = API_URL + '/' + method
        r = requests.get(url, params=params)

        if r.status_code == 200:
            data = r.json()
            return data
        else:
            return None

    #----------------------------------------------------------------------
    def processQueue(self):
        """处理请求队列中的请求"""
        while self.active:
            try:
                req = self.reqQueue.get(block=True, timeout=1)  # 获取请求的阻塞为一秒
                callback = req['callback']
                reqID = req['reqID']

                data = self.processRequest(req)
                # 请求失败
                if 'code' in data and 'message' in data:
                    error = u'错误信息：%s' %data['message']
                    self.onError(error, req, reqID)
                # 请求成功
                else:
                    if self.DEBUG:
                        print callback.__name__
                    callback(data, req, reqID)

            except Empty:
                pass

    #----------------------------------------------------------------------
    def sendRequest(self, method, params, callback):
        """发送请求"""
        # 请求编号加1
        self.reqID += 1

        # 生成请求字典并放入队列中
        req = {}
        req['method'] = method
        req['params'] = params
        req['callback'] = callback
        req['reqID'] = self.reqID
        self.reqQueue.put(req)

        # 返回请求编号
        return self.reqID

    ####################################################
    ## 主动函数
    ####################################################

    #----------------------------------------------------------------------
    def init(self, accessKey, secretKey):
        """初始化"""
        self.accessKey = accessKey
        self.secretKey = secretKey

        self.headers = {'X-MBX-APIKEY': self.accessKey}
        self.active = True
        self.reqThread.start()

    #----------------------------------------------------------------------
    def exit(self):
        """退出"""
        self.active = False

        if self.reqThread.isAlive():
            self.reqThread.join()

    def getProducts(self):
        method = METHOD_GET_PRODUCTS
        params = dict()
        callback = self.onProducts
        return self.sendRequest(method, params, callback)

    def getProduct(self, symbol):
        pass

  #----------------------------------------------------------------------
    def onError(self, error, req, reqID):
        """错误推送"""
        print error, reqID

  #----------------------------------------------------------------------
    def onProducts(self, data, req, reqID):
        """错误推送"""
        print data, reqID
