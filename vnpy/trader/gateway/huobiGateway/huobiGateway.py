# encoding: UTF-8

'''
vn.huobi的gateway接入
'''


import os
import json
from datetime import datetime
from copy import copy
from threading import Condition
from Queue import Queue
from threading import Thread

from vnpy.api.huobi import vnhuobi
from vnpy.trader.vtGateway import *
from vnpy.trader.vtFunction import getJsonPath

#BTC_USD_SPOT
BTC_USD_SPOT = 'BTC_USD_SPOT'
ETH_USD_SPOT = 'ETH_USD_SPOT'
LTC_USD_SPOT = 'LTC_USD_SPOT'
ETH_BTC_SPOT = 'ETH_BTC_SPOT'

SYMBOL_MAP = {}
SYMBOL_MAP['btcusdt'] = BTC_USD_SPOT
SYMBOL_MAP['ethusdt'] = ETH_USD_SPOT
SYMBOL_MAP['ltcusdt'] = LTC_USD_SPOT
SYMBOL_MAP['ethbtc'] = ETH_BTC_SPOT
SYMBOL_MAP_REVERSE = {v: k for k, v in SYMBOL_MAP.items()}

DIRECTION_MAP = {}
DIRECTION_MAP[1] = DIRECTION_LONG
DIRECTION_MAP[2] = DIRECTION_SHORT

STATUS_MAP = {}
STATUS_MAP[0] = STATUS_NOTTRADED
STATUS_MAP[1] = STATUS_PARTTRADED
STATUS_MAP[2] = STATUS_ALLTRADED
STATUS_MAP[3] = STATUS_CANCELLED
STATUS_MAP[5] = STATUS_UNKNOWN
STATUS_MAP[7] = STATUS_UNKNOWN



########################################################################
class HuobiGateway(VtGateway):
    """火币接口"""

    #----------------------------------------------------------------------
    def __init__(self, eventEngine, gatewayName='HUOBI'):
        """Constructor"""
        super(HuobiGateway, self).__init__(eventEngine, gatewayName)
        
        self.market = 'cny'
        
        self.tradeApi = HuobiTradeApi(self)
        self.dataApi = HuobiDataApi(self)
        #self.websocketApi =
        
        self.fileName = self.gatewayName + '_connect.json'
        self.filePath = getJsonPath(self.fileName, __file__)             
        
    #----------------------------------------------------------------------
    def connect(self):
        """连接"""
        # 载入json文件
        try:
            f = file(self.filePath)
        except IOError:
            log = VtLogData()
            log.gatewayName = self.gatewayName
            log.logContent = u'读取连接配置出错，请检查'
            self.onLog(log)
            return
        
        # 解析json文件
        setting = json.load(f)
        try:
            accessKey = str(setting['accessKey'])
            secretKey = str(setting['secretKey'])
            interval = setting['interval']
            market = setting['market']
            debug = setting['debug']
        except KeyError:
            log = VtLogData()
            log.gatewayName = self.gatewayName
            log.logContent = u'连接配置缺少字段，请检查'
            self.onLog(log)
            return            
        
        # 初始化接口
        self.tradeApi.connect(accessKey, secretKey, market, debug)
        self.writeLog(u'交易接口初始化成功')
        
        self.dataApi.connect(interval, market, debug)
        self.writeLog(u'行情接口初始化成功')
        
        # 启动查询
        self.initQuery()
        self.startQuery()
        
    #----------------------------------------------------------------------
    def writeLog(self, content):
        """发出日志"""
        log = VtLogData()
        log.gatewayName = self.gatewayName
        log.logContent = content
        self.onLog(log)        
    
    #----------------------------------------------------------------------
    def subscribe(self, subscribeReq):
        """订阅行情，自动订阅全部行情，无需实现"""
        pass
        
    #----------------------------------------------------------------------
    def sendOrder(self, orderReq):
        """发单"""
        self.tradeApi.sendOrder(orderReq)
        
    #----------------------------------------------------------------------
    def cancelOrder(self, cancelOrderReq):
        """撤单"""
        self.tradeApi.cancel(cancelOrderReq)
        
    #----------------------------------------------------------------------
    def qryAccount(self):
        """查询账户资金"""
        pass
        
    #----------------------------------------------------------------------
    def qryPosition(self):
        """查询持仓"""
        pass
        
    #----------------------------------------------------------------------
    def close(self):
        """关闭"""
        self.tradeApi.exit()
        self.dataApi.exit()
        
    #----------------------------------------------------------------------
    def initQuery(self):
        """初始化连续查询"""
        if self.qryEnabled:
            self.qryFunctionList = [self.tradeApi.queryWorkingOrders, self.tradeApi.queryAccount]
            self.startQuery()  
    
    #----------------------------------------------------------------------
    def query(self, event):
        """注册到事件处理引擎上的查询函数"""
        for function in self.qryFunctionList:
            function()
                
    #----------------------------------------------------------------------
    def startQuery(self):
        """启动连续查询"""
        self.eventEngine.register(EVENT_TIMER, self.query)
    
    #----------------------------------------------------------------------
    def setQryEnabled(self, qryEnabled):
        """设置是否要启动循环查询"""
        self.qryEnabled = qryEnabled
    

########################################################################
class HuobiTradeApi(vnhuobi.TradeApi):
    """交易接口"""

    #----------------------------------------------------------------------
    def __init__(self, gateway):
        """Constructor"""
        super(HuobiTradeApi, self).__init__()
        
        self.gateway = gateway
        self.gatewayName = gateway.gatewayName

        self.subscribeSet = set()    # 订阅的币种

        self.currency = {'btc', 'usdt', 'eth'}
        self.subscribeSymbol = set()
        self.localID = 0            # 本地委托号
        self.localSystemDict = {}   # key:localID, value:systemID
        self.systemLocalDict = {}   # key:systemID, value:localID
        self.workingOrderDict = {}  # key:localID, value:order
        self.reqLocalDict = {}      # key:reqID, value:localID
        self.cancelDict = {}        # key:localID, value:cancelOrderReq

        self.tradeID = 0            # 本地成交号


    #----------------------------------------------------------------------
    def onError(self, error, req, reqID):
        """错误推送"""
        err = VtErrorData()
        err.gatewayName = self.gatewayName
        err.errorMsg = str(error)
        err.errorTime = datetime.now().strftime('%H:%M:%S')
        self.gateway.onError(err)

    #----------------------------------------------------------------------
    def onGetAccountInfo(self, data, req, reqID):
        """查询账户回调"""
        # 推送账户数据
        postionDict = {}
        for e in data['data']['list']:
            if e['currency'] in postionDict:
                pos = postionDict[e['currency']]
                if 'trade' in e:
                    pos.position += e['balance']
                else:
                    pos.position += e['balance']
                    pos.frozen += e['balance']
            else:
                pos = VtPositionData()
                pos.gatewayName = self.gatewayName
                pos.symbol = e['currency']
                pos.exchange = EXCHANGE_HUOBI
                pos.vtSymbol = '.'.join([pos.symbol, pos.exchange])
                pos.vtPositionName = pos.vtSymbol
                if 'trade' in e:
                    pos.position = e['balance']
                    pos.frozen = 0
                else:
                    pos.position = e['balance']
                    pos.frozen = e['balance']
                postionDict[pos.symbol] = pos

        for symbol in postionDict.keys():
            if symbol == 'usdt':
                account = VtAccountData()
                account.gatewayName = self.gatewayName
                account.accountID = 'HUOBI'
                account.vtAccountID = '.'.join([account.accountID, self.gatewayName])
                account.balance = postionDict[symbol].position
                self.gateway.onAccount(account)

            if symbol in (self.currency | self.subscribeSymbol):
                self.gateway.onPosition(postionDict[symbol])

    #----------------------------------------------------------------------
    def onGetOrders(self, data, req, reqID):
        """查询委托回调"""
        for d in data:
            order = VtOrderData()
            order.gatewayName = self.gatewayName

            # 合约代码
            params = req['params']
            coin = params['coin_type']
            order.symbol = SYMBOL_MAP[(coin, self.market)]
            order.exchange = EXCHANGE_HUOBI
            order.vtSymbol = '.'.join([order.symbol, order.exchange])

            # 委托号
            systemID = d['id']
            self.localID += 1
            localID = str(self.localID)
            self.systemLocalDict[systemID] = localID
            self.localSystemDict[localID] = systemID
            order.orderID = localID
            order.vtOrderID = '.'.join([order.orderID, order.gatewayName])

            # 其他信息
            order.direction = DIRECTION_MAP[d['type']]
            order.offset = OFFSET_NONE
            order.price = float(d['order_price'])
            order.totalVolume = float(d['order_amount'])
            order.tradedVolume = float(d['processed_amount'])
            order.orderTime = d['order_time']

            # 委托状态
            if order.tradedVolume == 0:
                order.status = STATUS_NOTTRADED
            else:
                order.status = STATUS_PARTTRADED

            # 缓存病推送
            self.workingOrderDict[localID] = order
            self.gateway.onOrder(order)

    #----------------------------------------------------------------------
    def onOrderInfo(self, data, req, reqID):
        """委托详情回调"""
        systemID = data['id']
        localID = self.systemLocalDict[systemID]
        order = self.workingOrderDict.get(localID, None)
        if not order:
            return

        # 记录最新成交的金额
        newTradeVolume = float(data['processed_amount']) - order.tradedVolume
        if newTradeVolume:
            trade = VtTradeData()
            trade.gatewayName = self.gatewayName
            trade.symbol = order.symbol
            trade.vtSymbol = order.vtSymbol

            self.tradeID += 1
            trade.tradeID = str(self.tradeID)
            trade.vtTradeID = '.'.join([trade.tradeID, trade.gatewayName])

            trade.volume = newTradeVolume
            trade.price = data['processed_price']
            trade.direction = order.direction
            trade.offset = order.offset
            trade.exchange = order.exchange
            trade.tradeTime = datetime.now().strftime('%H:%M:%S')

            self.gateway.onTrade(trade)

        # 更新委托状态
        order.tradedVolume = float(data['processed_amount'])
        order.status = STATUS_MAP.get(data['status'], STATUS_UNKNOWN)

        if newTradeVolume:
            self.gateway.onOrder(order)

        if order.status == STATUS_ALLTRADED or order.status == STATUS_CANCELLED:
            del self.workingOrderDict[order.orderID]

    #----------------------------------------------------------------------
    def onBuy(self, data, req, reqID):
        """买入回调"""
        localID = self.reqLocalDict[reqID]
        systemID = data['id']
        self.localSystemDict[localID] = systemID
        self.systemLocalDict[systemID] = localID

        # 撤单
        if localID in self.cancelDict:
            req = self.cancelDict[localID]
            self.cancel(req)
            del self.cancelDict[localID]

        # 推送委托信息
        order = self.workingOrderDict[localID]
        if data['result'] == 'success':
            order.status = STATUS_NOTTRADED
        self.gateway.onOrder(order)
        
    #----------------------------------------------------------------------
    def onSell(self, data, req, reqID):
        """卖出回调"""
        localID = self.reqLocalDict[reqID]
        systemID = data['id']
        self.localSystemDict[localID] = systemID
        self.systemLocalDict[systemID] = localID

        # 撤单
        if localID in self.cancelDict:
            req = self.cancelDict[localID]
            self.cancel(req)
            del self.cancelDict[localID]

        # 推送委托信息
        order = self.workingOrderDict[localID]
        if data['result'] == 'success':
            order.status = STATUS_NOTTRADED
        self.gateway.onOrder(order)

    #----------------------------------------------------------------------
    def onCancelOrder(self, data, req, reqID):
        """撤单回调"""
        if data['result'] == 'success':
            systemID = req['params']['id']
            localID = self.systemLocalDict[systemID]

            order = self.workingOrderDict[localID]
            order.status = STATUS_CANCELLED

            del self.workingOrderDict[localID]
            self.gateway.onOrder(order)

    #----------------------------------------------------------------------
    def connect(self, accessKey, secretKey, market, debug=False):
        """连接服务器"""
        self.market = market
        self.DEBUG = debug
        
        self.init(accessKey, secretKey)
        self.getAccountInfo()

        # 查询未成交委托
        # self.getOrders(vnhuobi.COINTYPE_BTC, self.market)
        #
        # if self.market == vnhuobi.MARKETTYPE_CNY:
        #     # 只有人民币市场才有莱特币
        #     self.getOrders(vnhuobi.COINTYPE_LTC, self.market)

    # ----------------------------------------------------------------------
    def subscribe(self, symbol):
        self.subscribeSet.add(symbol)

    # ----------------------------------------------------------------------
    def queryWorkingOrders(self):
        """查询活动委托状态"""
        for order in self.workingOrderDict.values():
            # 如果尚未返回委托号，则无法查询
            if order.orderID in self.localSystemDict:
                systemID = self.localSystemDict[order.orderID]
                coin, market = SYMBOL_MAP_REVERSE[order.symbol]
                self.orderInfo(systemID, coin, market)

    # ----------------------------------------------------------------------
    def queryAccount(self):
        """查询活动委托状态"""
        self.getAccountInfo()

    # ----------------------------------------------------------------------
    def sendOrder(self, req):
        """发送委托"""
        # 检查是否填入了价格，禁止市价委托
        if req.priceType != PRICETYPE_LIMITPRICE:
            err = VtErrorData()
            err.gatewayName = self.gatewayName
            err.errorMsg = u'火币接口仅支持限价单'
            err.errorTime = datetime.now().strftime('%H:%M:%S')
            self.gateway.onError(err)
            return None

        # 发送限价委托
        coin, market = SYMBOL_MAP_REVERSE[req.symbol]

        if req.direction == DIRECTION_LONG:
            reqID = self.buy(req.price, req.volume, coinType=coin, market=self.market)
        else:
            reqID = self.sell(req.price, req.volume, coinType=coin, market=self.market)

        self.localID += 1
        localID = str(self.localID)
        self.reqLocalDict[reqID] = localID

        # 推送委托信息
        order = VtOrderData()
        order.gatewayName = self.gatewayName

        order.symbol = req.symbol
        order.exchange = EXCHANGE_HUOBI
        order.vtSymbol = '.'.join([order.symbol, order.exchange])

        order.orderID = localID
        order.vtOrderID = '.'.join([order.orderID, order.gatewayName])

        order.direction = req.direction
        order.offset = OFFSET_UNKNOWN
        order.price = req.price
        order.volume = req.volume
        order.orderTime = datetime.now().strftime('%H:%M:%S')
        order.status = STATUS_UNKNOWN

        self.workingOrderDict[localID] = order
        self.gateway.onOrder(order)

        # 返回委托号
        return order.vtOrderID

    # ----------------------------------------------------------------------
    def cancel(self, req):
        """撤单"""
        localID = req.orderID
        if localID in self.localSystemDict:
            systemID = self.localSystemDict[localID]
            coin, market = SYMBOL_MAP_REVERSE[req.symbol]
            self.cancelOrder(systemID, coin, self.market)
        else:
            self.cancelDict[localID] = req



########################################################################
class HuobiDataApi(vnhuobi.DataApi):
    """行情接口"""

    #----------------------------------------------------------------------
    def __init__(self, gateway):
        """Constructor"""
        super(HuobiDataApi, self).__init__()

        self.market = 'cny'
        
        self.gateway = gateway
        self.gatewayName = gateway.gatewayName

        self.tickDict = {}      # key:symbol, value:tick

    def readData(self, evt):
        """解压缩推送收到的数据"""
        # 通过json解析字符串
        data = json.loads(evt)

        return data

    #----------------------------------------------------------------------
    def onTick(self, data):
        """实时成交推送"""
        print data

    #----------------------------------------------------------------------
    def onDepth(self, data):
        """实时深度推送"""
        data = self.readData(data)
        data = data['tick']
        chsymbol = data['ch'].split('.')[1]
        symbol = SYMBOL_MAP[chsymbol]
        if symbol not in self.tickDict:
            tick = VtTickData()
            tick.gatewayName = self.gatewayName

            tick.symbol = symbol
            tick.exchange = EXCHANGE_HUOBI
            tick.vtSymbol = '.'.join([tick.symbol, tick.exchange])
            self.tickDict[symbol] = tick
        else:
            tick = self.tickDict[symbol]

        tick.bidPrice1, tick.bidVolume1 = data['bids'][0]
        tick.bidPrice2, tick.bidVolume2 = data['bids'][1]
        tick.bidPrice3, tick.bidVolume3 = data['bids'][2]
        tick.bidPrice4, tick.bidVolume4 = data['bids'][3]
        tick.bidPrice5, tick.bidVolume5 = data['bids'][4]

        tick.askPrice1, tick.askVolume1 = data['asks'][0]
        tick.askPrice2, tick.askVolume2 = data['asks'][1]
        tick.askPrice3, tick.askVolume3 = data['asks'][2]
        tick.askPrice4, tick.askVolume4 = data['asks'][3]
        tick.askPrice5, tick.askVolume5 = data['asks'][4]

        now = datetime.now()
        tick.time = now.strftime('%H:%M:%S.%f')
        tick.date = now.strftime('%Y%m%d')

        self.gateway.onTick(tick)

    #----------------------------------------------------------------------
    def subscribe(self, symbol):
        """订阅行情信息"""
        _symbol = SYMBOL_MAP_REVERSE[symbol]
        self.subscribeDepth(_symbol)

        contract = VtContractData()
        contract.gatewayName = self.gatewayName
        contract.symbol = symbol
        contract.exchange = EXCHANGE_HUOBI
        contract.vtSymbol = '.'.join([contract.symbol, contract.exchange])
        contract.name = u'币币交易'
        contract.size = 1
        contract.priceTick = 0.001
        contract.productClass = PRODUCT_SPOT
        self.gateway.onContract(contract)


    #----------------------------------------------------------------------
    def connect(self, interval, market, debug=False):
        """连接服务器"""
        self.market = market
        self.init(interval, debug)


