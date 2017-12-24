# encoding: utf-8

import urllib

import requests
from time import time, sleep
from Queue import Queue, Empty
from threading import Thread

import websocket
import gzip
import StringIO
import base64
import hmac
import hashlib
import json
import datetime
import urlparse

TIMEOUT = 5


# API相关定义
HUOBI_TRADE_API = 'https://api.huobi.pro'
HUOBI_MARKET_API = 'https://api.huobi.pro/market'
HUOBI_WEBSOCKET_WSS = 'wss://api.huobi.pro/ws'

# 功能代码
FUNCTIONCODE_GETACCOUNTINFO = '/v1/account/accounts'
FUNCTIONCODE_GEBANLANCE = '/v1/account/accounts/%s/balance'
FUNCTIONCODE_PLACEORDER = '/v1/order/orders/place'
FUNCTIONCODE_CANCELORDER = '/v1/order/orders/%s/submitcancel'


SYMBOL_ETHBTC = 'ethbtc'
SYMBOL_LTCBTC = 'ltcbtc'
SYMBOL_BTCUSDT = 'btcusdt'

PERIOD_1MIN = '1min'
PERIOD_5MIN = '5min'
PERIOD_15MIN = '15min'
PERIOD_30MIN = '30min'
PERIOD_60MIN = '60min'
PERIOD_DAILY = '1day'
PERIOD_WEEKLY = '1week'
PERIOD_MONTHLY = '1mon'
PERIOD_ANNUALLY = '1year'

DEPTH_STEP0 = 'step0'
DEPTH_STEP1 = 'step1'
DEPTH_STEP2 = 'step2'
DEPTH_STEP3 = 'step3'
DEPTH_STEP4 = 'step4'


########################################################################
def http_get_request(url, params, add_to_headers=None):
    headers = {
        "Content-type": "application/x-www-form-urlencoded",
        'User-Agent':'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:53.0) Gecko/20100101 Firefox/53.0'
    }
    if add_to_headers:
        headers.update(add_to_headers)
    postdata = urllib.urlencode(params)
    try:
        response = requests.get(url, postdata, headers=headers, timeout=TIMEOUT)
        if response.status_code == 200:
            return response.json()
        else:
            return {"status":"fail"}
    except Exception as e:
        print("httpGet failed, detail is:%s" %e)
        return {"status":"fail","msg":e}


########################################################################
def http_post_request(url, params, add_to_headers=None):
    headers = {
        "Accept": "application/json",
        'Content-Type': 'application/json',
        "User-Agent": "Chrome/39.0.2171.71",
        'User-Agent':'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:53.0) Gecko/20100101 Firefox/53.0'
    }
    if add_to_headers:
        headers.update(add_to_headers)
    postdata = json.dumps(params)
    try:
        response = requests.post(url, postdata, headers=headers, timeout=TIMEOUT)
        if response.status_code == 200:
            return response.json()
        else:
            return response.json()
    except Exception as e:
        print("httpPost failed, detail is:%s" % e)
        return {"status":"fail","msg":e}


########################################################################
def createSign(pParams, method, host_url, request_path, secret_key):
    sorted_params = sorted(pParams.items(), key=lambda d: d[0], reverse=False)
    encode_params = urllib.urlencode(sorted_params)
    payload = [method, host_url, request_path, encode_params]
    payload = '\n'.join(payload)
    payload = payload.encode(encoding='UTF8')
    secret_key = secret_key.encode(encoding='UTF8')
    digest = hmac.new(secret_key, payload, digestmod=hashlib.sha256).digest()
    signature = base64.b64encode(digest)
    signature = signature.decode()
    return signature


########################################################################
class DataApi(object):
    """行情接口"""

    TICK_URL = HUOBI_MARKET_API + "/detail/merged"
    DEPTH_URL = HUOBI_MARKET_API + "/depth"
    KLINE_URL = HUOBI_MARKET_API + "/history/kline"

    DEBUG = True

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        self.active = False

        self.taskInterval = 0                       # 每轮请求延时
        self.taskList = []                          # 订阅的任务列表
        self.taskThread = Thread(target=self.run)   # 处理任务的线程

        self.headers = {'User-Agent':
                           'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36'}

    #----------------------------------------------------------------------
    def init(self, interval, debug):
        """初始化"""
        self.taskInterval = interval
        self.DEBUG = debug

        self.active = True
        self.taskThread.start()

    #----------------------------------------------------------------------
    def exit(self):
        """退出"""
        self.active = False

        if self.taskThread.isAlive():
            self.taskThread.join()

    #----------------------------------------------------------------------
    def run(self):
        """连续运行"""
        while self.active:
            for url, callback in self.taskList:
                try:
                    r = requests.get(url, headers=self.headers)
                    if r.status_code == 200:
                        data = r.json()
                        if self.DEBUG:
                            print callback.__name__
                        callback(data)
                except Exception, e:
                    print e

            sleep(self.taskInterval)

# ----------------------------------------------------------------------
    def getKline(self, symbol, period="1min"):
        """订阅实时成交数据"""
        url = self.TICK_URL + "?symbol=" + symbol + "&period=" + period
        try:
            r = requests.get(url, headers=self.headers)
            if r.status_code == 200:
                data = r.json()
                return data
        except Exception, e:
            print e
            return None


    #----------------------------------------------------------------------
    def subscribeTick(self, symbol):
        """订阅实时成交数据"""
        url = self.TICK_URL + "?symbol=" + symbol
        task = (url, self.onTick)
        self.taskList.append(task)

    #----------------------------------------------------------------------
    def subscribeDepth(self, symbol, step='step0'):
        """订阅深度数据"""
        url = self.DEPTH_URL + "?symbol=" + symbol + "&type=" + step
        task = (url, self.onDepth)
        self.taskList.append(task)

    #----------------------------------------------------------------------
    def onTick(self, data):
        """实时成交推送"""
        print data

    #----------------------------------------------------------------------
    def onKline(self, data):
        """实时报价推送"""
        print data

    #----------------------------------------------------------------------
    def onDepth(self, data):
        """实时深度推送"""
        print data


########################################################################
class TradeApi(object):
    """交易接口"""
    DEBUG = True

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        self.accessKey = ''
        self.secretKey = ''

        self.account_id = None
        self.active = False         # API工作状态   
        self.reqID = 0              # 请求编号
        self.reqQueue = Queue()     # 请求队列
        self.reqThread = Thread(target=self.processQueue)   # 请求处理线程        


    #----------------------------------------------------------------------
    def processRequest(self, req):
        """处理请求"""
        # 读取方法和参数
        http_method = req['http_method']
        method = req['method']
        params = req['params']

        if http_method == 'GET':
            timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
            params.update({'AccessKeyId': self.accessKey,
                           'SignatureMethod': 'HmacSHA256',
                           'SignatureVersion': '2',
                           'Timestamp': timestamp})

            host_name = host_url = HUOBI_TRADE_API
            host_name = urlparse.urlparse(host_url).hostname
            host_name = host_name.lower()

            params['Signature'] = createSign(params, http_method, host_name, method, self.secretKey)
            url = host_url + method
            print url
            return http_get_request(url, params)
        elif http_method == 'POST':
            timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
            params_to_sign = {'AccessKeyId': self.accessKey,
                              'SignatureMethod': 'HmacSHA256',
                              'SignatureVersion': '2',
                              'Timestamp': timestamp}

            host_url = HUOBI_TRADE_API
            host_name = urlparse.urlparse(host_url).hostname
            host_name = host_name.lower()
            params_to_sign['Signature'] = createSign(params_to_sign, http_method, host_name, method, self.secretKey)
            url = host_url + method + '?' + urllib.urlencode(params_to_sign)
            return http_post_request(url, params)
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
    def sendRequest(self, http_method, method, params, callback, optional=None):
        """发送请求"""
        # 请求编号加1
        self.reqID += 1
        
        # 生成请求字典并放入队列中
        req = {}
        req['http_method'] = http_method
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
    def getAccountInfo(self):
        """查询账户"""
        http_method = 'GET'
        method = FUNCTIONCODE_GETACCOUNTINFO
        params = {}
        callback = self.onGetAccountInfo
        return self.sendRequest(http_method, method, params, callback)

    #----------------------------------------------------------------------
    def getBalance(self):
        """查询余额"""
        if self.account_id is None:
            self.getAccountInfo()
            return

        http_method = 'GET'
        method = FUNCTIONCODE_GEBANLANCE % self.account_id
        params = {}
        callback = self.onGetBalance
        return self.sendRequest(http_method, method, params, callback)


    #----------------------------------------------------------------------
    def buy(self, price, amount, symbol):
        """委托买入"""
        method = FUNCTIONCODE_PLACEORDER
        http_method = "POST"
        params = {
            "account-id": self.account_id,
            "amount": amount,
            "price": price,
            "source": "api",
            "symbol": symbol,
            "type": "buy-limit"
        }
        callback = self.onBuy
        return self.sendRequest(http_method, method, params, callback)

    #----------------------------------------------------------------------
    def sell(self, price, amount, symbol):
        """委托卖出"""
        method = FUNCTIONCODE_PLACEORDER
        http_method = "POST"
        params = {
            "account-id": self.account_id,
            "amount": amount,
            "price": price,
            "source": "api",
            "symbol": symbol,
            "type": "sell-limit"
        }
        callback = self.onSell
        return self.sendRequest(http_method, method, params, callback)
    
    #----------------------------------------------------------------------
    def buyMarket(self, amount, symbol):
        """市价买入"""
        method = FUNCTIONCODE_PLACEORDER
        http_method = "POST"
        params = {
            "account-id": self.account_id,
            "amount": amount,
            "source": "api",
            "symbol": symbol,
            "type": "buy-market"
        }
        callback = self.onBuyMarket
        return self.sendRequest(http_method, method, params, callback)
    
    #----------------------------------------------------------------------
    def sellMarket(self, amount, symbol):
        """市价卖出"""
        method = FUNCTIONCODE_PLACEORDER
        http_method = "POST"
        params = {
            "account-id": self.account_id,
            "amount": amount,
            "source": "api",
            "symbol": symbol,
            "type": "sell-market"
        }
        callback = self.onSellMarket
        return self.sendRequest(http_method, method, params, callback)
    
    #----------------------------------------------------------------------
    def cancelOrder(self, order_id):
        """撤销委托"""
        method = FUNCTIONCODE_CANCELORDER % order_id
        http_method = "POST"
        params = {}
        callback = self.onCancelOrder
        return self.sendRequest(http_method, method, params, callback)

    ####################################################
    ## 回调函数
    ####################################################
    
    #----------------------------------------------------------------------
    def onError(self, error, req, reqID):
        """错误推送"""
        print error, reqID    

    #----------------------------------------------------------------------
    def onGetAccountInfo(self, data, req, reqID):
        """查询账户回调"""
        self.account_id = data['data'][0]['id']
        print data

    #----------------------------------------------------------------------
    def onGetBalance(self, data, req, reqID):
        """查询账户回调"""
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
    

class DataWebSocketApi(object):
        #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        self.apiKey = ''        # 用户名
        self.secretKey = ''     # 密码
        self.host = ''          # 服务器地址

        self.ws = None          # websocket应用对象
        self.thread = None      # 工作线程

    #######################
    ## 通用函数
    #######################

    #----------------------------------------------------------------------
    def readData(self, evt):
        """解压缩推送收到的数据"""
        # 通过json解析字符串
        compressedstream = StringIO.StringIO(evt)
        gzipper = gzip.GzipFile(fileobj=compressedstream)
        json_data = gzipper.read() # data就是解压后的数据
        data = json.loads(json_data)
        return data

    #----------------------------------------------------------------------
    def onMessage(self, ws, evt):
        """信息推送"""
        print 'onMessage'
        data = self.readData(evt)
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
    def connect(self, host, apiKey, secretKey, trace=False):
        """连接服务器"""
        self.host = host
        self.apiKey = apiKey
        self.secretKey = secretKey

        websocket.enableTrace(trace)

        self.ws = websocket.WebSocketApp(host,
                                         on_message=self.onMessage,
                                         on_error=self.onError,
                                         on_close=self.onClose,
                                         on_open=self.onOpen)

        self.thread = Thread(target=self.ws.run_forever)
        self.thread.start()

    #----------------------------------------------------------------------
    def reconnect(self):
        """重新连接"""
        # 首先关闭之前的连接
        self.close()

        # 再执行重连任务
        self.ws = websocket.WebSocketApp(self.host,
                                         on_message=self.onMessage,
                                         on_error=self.onError,
                                         on_close=self.onClose,
                                         on_open=self.onOpen)

        self.thread = Thread(target=self.ws.run_forever)
        self.thread.start()

    #----------------------------------------------------------------------
    def close(self):
        """关闭接口"""
        if self.thread and self.thread.isAlive():
            self.ws.close()
            self.thread.join()

    #----------------------------------------------------------------------
    def pong(self, number):
        d = {}
        d['pong'] = number
        j = json.dumps(d)
        try:
            self.ws.send(j)
        except websocket.WebSocketConnectionClosedException:
            pass

    #---------------------------------------------------
    def sendDepthDataRequest(self, symbol, depth_type):
        d = {}
        d['sub'] = "market.%s.depth.%s" % (symbol, depth_type)
        d['id'] = "id10"
        j = json.dumps(d)
        print j
        try:
            self.ws.send(j)
        except websocket.WebSocketConnectionClosedException:
            pass

    #---------------------------------------------------
    def sendKlineDataRequest(self, symbol, period):
        d = {}
        d['sub'] = "market.%s.kline.%s" % (symbol, period)
        d['id'] = "id9"
        j = json.dumps(d)
        print j
        try:
            self.ws.send(j)
        except websocket.WebSocketConnectionClosedException:
            pass

    #---------------------------------------------------
    def sendTradeDetailDataRequest(self, symbol):
        d = {}
        d['sub'] = "market.%s.trade.detail" % (symbol)
        d['id'] = "id8"
        j = json.dumps(d)
        print j
        try:
            self.ws.send(j)
        except websocket.WebSocketConnectionClosedException:
            pass

    #---------------------------------------------------
    def sendMarketDetailDataRequest(self, symbol):
        d = {}
        d['sub'] = "market.%s.detail" % (symbol)
        d['id'] = "id7"
        j = json.dumps(d)
        print j
        try:
            self.ws.send(j)
        except websocket.WebSocketConnectionClosedException:
            pass

