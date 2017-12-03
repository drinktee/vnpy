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

import websocket

# Binance
BINANCE_HOST = 'wss://stream.binance.com:9443/ws/'
BINANCE_API_URL = "https://api.binance.com/api/"

PRIVATE_API_VERSION = 'v3'
PUBLIC_API_VERSION = 'v1'

METHOD_TEST_CONNECT = 'ping'
METHOD_TIME = 'time'
METHOD_DEPTH = 'depth'
METHOD_KLINE = 'klines'
METHOD_ACCOUNT = 'account'


SYMBOL_LTC_BTC = 'LTCBTC'
SYMBOL_BNB_BTC = 'BNBBTC'

# 行情深度
DEPTH_5 = 5
DEPTH_20 = 20
DEPTH_100 = 100

# K线时间区间
INTERVAL_1M = '1m'
INTERVAL_3M = '3m'
INTERVAL_5M = '5m'
INTERVAL_15M = '15m'
INTERVAL_30M = '30m'
INTERVAL_1H = '1h'
INTERVAL_2H = '2h'
INTERVAL_4H = '4h'
INTERVAL_6H = '6h'


########################################################################
class DataApi(object):
    """基于Websocket的API对象"""
    # ----------------------------------------------------------------------
    def __init__(self, api_key=""):
        """Constructor"""
        self.api_key = api_key
        self.threads = []      # 工作线程

    #######################
    ## 通用函数
    #######################
    # ----------------------------------------------------------------------
    def onMessage(self, ws, data):
        """信息推送"""
        print 'onMessage'
        print data

    #----------------------------------------------------------------------
    def onError(self, ws, evt):
        """错误推送"""
        print 'onError'
        print evt

    #----------------------------------------------------------------------
    def onClose(self, ws):
        """接口断开"""
        print 'onClose'

    #----------------------------------------------------------------------
    def onOpen(self, ws):
        """接口打开"""
        print 'onOpen'

    #----------------------------------------------------------------------
    def subscribeDepth(self, symbol, trace=False):
        """订阅实时深度详情"""
        url = BINANCE_HOST + symbol + '@depth'
        websocket.enableTrace(trace)
        ws = websocket.WebSocketApp(url,
                                         on_message=self.onMessage,
                                         on_error=self.onError,
                                         on_close=self.onClose,
                                         on_open=self.onOpen)

        thread = Thread(target=ws.run_forever)
        thread.start()
        self.threads.append((ws, thread))

    #----------------------------------------------------------------------
    def subscribeKline(self, symbol, interval, trace=False):
        """订阅实时k线详情"""
        url = BINANCE_HOST + symbol + '@kline_' + interval
        websocket.enableTrace(trace)
        ws = websocket.WebSocketApp(url,
                                         on_message=self.onMessage,
                                         on_error=self.onError,
                                         on_close=self.onClose,
                                         on_open=self.onOpen)

        thread = Thread(target=ws.run_forever)
        thread.start()
        self.threads.append((ws, thread))

       #----------------------------------------------------------------------
    def subscribeTrade(self, symbol, trace=False):
        """订阅实时交易详情"""
        url = BINANCE_HOST + symbol + '@aggTrade'
        websocket.enableTrace(trace)
        ws = websocket.WebSocketApp(url,
                                         on_message=self.onMessage,
                                         on_error=self.onError,
                                         on_close=self.onClose,
                                         on_open=self.onOpen)

        thread = Thread(target=ws.run_forever)
        thread.start()
        self.threads.append((ws, thread))

    #----------------------------------------------------------------------
    def close(self):
        """关闭接口"""
        for (ws, thread) in self.threads:
            ws.close()
            thread.join()


########################################################################
class TradeApi(object):
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
        params = sorted(params.items())
        message = urllib.urlencode(params)
        m = hmac.new(bytes(self.secretKey.encode('utf-8')), message.encode('utf-8'), hashlib.sha256)
        sig = m.hexdigest()
        return sig

    #----------------------------------------------------------------------
    def processRequest(self, req):
        """处理请求"""
        method = req['method']
        params = req['params']
        signed = req['signed']

        url = BINANCE_API_URL + signed + '/' + method
        if signed == PUBLIC_API_VERSION:
            r = requests.get(url, params=params)
        else:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self.signature(params)
            print url, params, self.headers
            r = requests.get(url, params=params, headers=self.headers)
            print r.json()

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
    def sendRequest(self, method, params, api_version, callback):
        """发送请求"""
        # 请求编号加1
        self.reqID += 1

        # 生成请求字典并放入队列中
        req = {}
        req['signed'] = api_version
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

    #----------------------------------------------------------------------
    def getDepth(self, symbol, depth=DEPTH_100):
        method = METHOD_DEPTH
        params = dict()
        params['symbol'] = symbol
        params['limit'] = depth
        callback = self.onDepth
        return self.sendRequest(method, params, PUBLIC_API_VERSION, callback)


    #----------------------------------------------------------------------
    def getKline(self, symbol, interval=INTERVAL_1M, depth=DEPTH_100):
        method = METHOD_KLINE
        params = dict()
        params['symbol'] = symbol
        params['limit'] = depth
        params['interval'] = interval
        callback = self.onKlines
        return self.sendRequest(method, params, PUBLIC_API_VERSION, callback)

    #----------------------------------------------------------------------
    def getAccountInfo(self):
        """查询账户"""
        method = METHOD_ACCOUNT
        params = {}
        callback = self.onGetAccountInfo
        return self.sendRequest(method, params, PRIVATE_API_VERSION, callback)

    ####################################################
    ## 回调函数
    ####################################################

    #----------------------------------------------------------------------
    def onError(self, error, req, reqID):
        """错误推送"""
        print error, reqID

    #----------------------------------------------------------------------
    def onDepth(self, data, req, reqID):
        """错误推送"""
        print data, reqID

        #----------------------------------------------------------------------
    def onKlines(self, error, req, reqID):
        """错误推送"""
        print error, reqID

    #----------------------------------------------------------------------
    def onGetAccountInfo(self, data, req, reqID):
        """查询账户回调"""
        print data

    #----------------------------------------------------------------------
    def onGetOrders(self, data, req, reqID, fuck):
        """查询委托回调"""
        print data

    #----------------------------------------------------------------------
    def onOrderInfo(self, data, req, reqID):
        """委托详情回调"""
        print data

    #----------------------------------------------------------------------
    def onBuy(self, data, req, reqID):
        """买入回调"""
        print data

    #----------------------------------------------------------------------
    def onSell(self, data, req, reqID):
        """卖出回调"""
        print data

    #----------------------------------------------------------------------
    def onBuyMarket(self, data, req, reqID):
        """市价买入回调"""
        print data

    #----------------------------------------------------------------------
    def onSellMarket(self, data, req, reqID):
        """市价卖出回调"""
        print data

    #----------------------------------------------------------------------
    def onCancelOrder(self, data, req, reqID):
        """撤单回调"""
        print data

    #----------------------------------------------------------------------
    def onGetNewDealOrders(self, data, req, reqID):
        """查询最新成交回调"""
        print data