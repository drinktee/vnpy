# encoding: utf-8
from vnpy.trader.vtGateway import *
from vnpy.trader.vtFunction import getJsonPath

from vnpy.api.binance import vnbinance
import os
import json
class BinanceGateway(VtGateway):
    def __init__(self, eventEngine, gatewayName):
        super(BinanceGateway, self).__init__(eventEngine, gatewayName)
        self.market = 'cny'
        self.tradeApi = BinanceTradeApi(self)
        self.fileName = self.gatewayName + '_connect.json'
        self.filePath = getJsonPath(self.fileName, __file__)

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


    def writeLog(self, content):
        """发出日志"""
        log = VtLogData()
        log.gatewayName = self.gatewayName
        log.logContent = content
        self.onLog(log)





    #----------------------------------------------------------------------
    def initQuery(self):
        """初始化连续查询"""
        if self.qryEnabled:
            self.qryFunctionList = [self.tradeApi.queryWorkingOrders, self.tradeApi.queryAccount]
            self.startQuery()
            # ----------------------------------------------------------------------

    def startQuery(self):
        """启动连续查询"""
        self.eventEngine.register(EVENT_TIMER, self.query)

    # ----------------------------------------------------------------------
    def setQryEnabled(self, qryEnabled):
        """设置是否要启动循环查询"""
        self.qryEnabled = qryEnabled

    def query(self, event):
        """注册到事件处理引擎上的查询函数"""
        for function in self.qryFunctionList:
            function()




########################################################################
class BinanceTradeApi(vnbinance.TradeApi):
    """交易接口"""

    #----------------------------------------------------------------------
    def __init__(self, gateway):
        """Constructor"""
        super(BinanceTradeApi, self).__init__()
        
        self.gateway = gateway
        self.gatewayName = gateway.gatewayName

        self.subscribeSet = set()    # 订阅的币种

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
        for e in data['data']['list']:
            if e['currency'] == 'usdt':
                pass


        account = VtAccountData()
        account.gatewayName = self.gatewayName
        account.accountID = 'HUOBI'
        account.vtAccountID = '.'.join([account.accountID, self.gatewayName])
        account.balance = data['net_asset']
        self.gateway.onAccount(account)


        
        # 推送持仓数据
        if self.market == 'cny':
            posCny = VtPositionData()
            posCny.gatewayName = self.gatewayName
            posCny.symbol = 'CNY'
            posCny.exchange = EXCHANGE_HUOBI
            posCny.vtSymbol = '.'.join([posCny.symbol, posCny.exchange])
            posCny.vtPositionName = posCny.vtSymbol
            posCny.position = data['available_cny_display']
            posCny.frozen = data['frozen_cny_display']
            self.gateway.onPosition(posCny)
            
            posLtc = VtPositionData()
            posLtc.gatewayName = self.gatewayName
            posLtc.symbol = 'LTC'
            posLtc.exchange = EXCHANGE_HUOBI
            posLtc.vtSymbol = '.'.join([posLtc.symbol, posLtc.exchange])
            posLtc.vtPositionName = posLtc.vtSymbol
            posLtc.position = data['available_ltc_display']
            posLtc.frozen = data['frozen_ltc_display']
            self.gateway.onPosition(posLtc)
        else:
            posUsd = VtPositionData()
            posUsd.gatewayName = self.gatewayName
            posUsd.symbol = 'USD'
            posUsd.exchange = EXCHANGE_HUOBI
            posUsd.vtSymbol = '.'.join([posUsd.symbol, posUsd.exchange])
            posUsd.vtPositionName = posUsd.vtSymbol
            posUsd.position = data['available_usd_display']
            posUsd.frozen = data['frozen_usd_display']
            self.gateway.onPosition(posUsd)     
            
        posBtc = VtPositionData()
        posBtc.gatewayName = self.gatewayName
        posBtc.symbol = 'BTC'
        posBtc.exchange = EXCHANGE_HUOBI
        posBtc.vtSymbol = '.'.join([posBtc.symbol, posBtc.exchange])
        posBtc.vtPositionName = posBtc.vtSymbol
        posBtc.position = data['available_btc_display']
        posBtc.frozen = data['frozen_btc_display']
        self.gateway.onPosition(posBtc)        
    
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

        # 查询未成交委托
        self.getOrders(vnhuobi.COINTYPE_BTC, self.market)

        if self.market == vnhuobi.MARKETTYPE_CNY:
            # 只有人民币市场才有莱特币
            self.getOrders(vnhuobi.COINTYPE_LTC, self.market)

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

