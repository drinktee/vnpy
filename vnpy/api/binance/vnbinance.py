# encoding: UTF-8

import hashlib
import zlib
import json
from time import sleep
from threading import Thread
from Queue import Queue, Empty
import requests
import urllib

import websocket

# Binance
BINANCE_HOST = 'wss://stream.binance.com:9443/ws/'
BINANCE_API_URL = "https://api.binance.com/api"

PRIVATE_API_VERSION = 'v3'
PUBLIC_API_VERSION = 'v1'

#----------------------------------------------------------------------
def signature(params):
    """生成签名"""
    params = sorted(params.iteritems(), key=lambda d:d[0], reverse=False)
    message = urllib.urlencode(params)

    m = hashlib.md5()
    m.update(message)
    m.digest()

    sig=m.hexdigest()
    return sig

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
    def processRequest(self, req):
        """处理请求"""
        # 读取方法和参数
        method = req['method']
        params = req['params']
        optional = req['optional']

        # 在参数中增加必须的字段
        params['created'] = long(time())
        params['access_key'] = self.accessKey
        params['secret_key'] = self.secretKey
        params['method'] = method

        # 添加签名
        sign = signature(params)
        params['sign'] = sign
        del params['secret_key']

        # 添加选填参数
        if optional:
            params.update(optional)

        # 发送请求
        payload = urllib.urlencode(params)

        r = requests.post(HUOBI_TRADE_API, params=payload)
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
    def sendRequest(self, method, params, callback, optional=None):
        """发送请求"""
        # 请求编号加1
        self.reqID += 1

        # 生成请求字典并放入队列中
        req = {}
        req['method'] = method
        req['params'] = params
        req['callback'] = callback
        req['optional'] = optional
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

        self.active = True
        self.reqThread.start()

    #----------------------------------------------------------------------
    def exit(self):
        """退出"""
        self.active = False

        if self.reqThread.isAlive():
            self.reqThread.join()

    #----------------------------------------------------------------------
    def getAccountInfo(self, market='cny'):
        """查询账户"""
        method = FUNCTIONCODE_GETACCOUNTINFO
        params = {}
        callback = self.onGetAccountInfo
        optional = {'market': market}
        return self.sendRequest(method, params, callback, optional)