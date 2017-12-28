# encoding: utf-8

from vnpy.trader.vtGateway import *

from vnpy.trader.vtFunction import getJsonPath
from datetime import datetime
from vnpy.api.binan import vnbinance
import time
import json

# USD
BTC_USD_SPOT = 'BTC_USD_SPOT'
BTC_USD_THISWEEK = 'BTC_USD_THISWEEK'
BTC_USD_NEXTWEEK = 'BTC_USD_NEXTWEEK'
BTC_USD_QUARTER = 'BTC_USD_QUARTER'

LTC_USD_SPOT = 'LTC_USD_SPOT'
LTC_USD_THISWEEK = 'LTC_USD_THISWEEK'
LTC_USD_NEXTWEEK = 'LTC_USD_NEXTWEEK'
LTC_USD_QUARTER = 'LTC_USD_QUARTER'

ETH_USD_SPOT = 'ETH_USD_SPOT'
ETH_USD_THISWEEK = 'ETH_USD_THISWEEK'
ETH_USD_NEXTWEEK = 'ETH_USD_NEXTWEEK'
ETH_USD_QUARTER = 'ETH_USD_QUARTER'

# BTC
LTC_BTC_SPOT = 'LTC_BTC_SPOT'
ETH_BTC_SPOT = 'ETH_BTC_SPOT'

# 价格类型映射
priceTypeMap = {}
priceTypeMap['BUY'] = (DIRECTION_LONG, PRICETYPE_LIMITPRICE)
priceTypeMap['buy_market'] = (DIRECTION_LONG, PRICETYPE_MARKETPRICE)
priceTypeMap['SELL'] = (DIRECTION_SHORT, PRICETYPE_LIMITPRICE)
priceTypeMap['sell_market'] = (DIRECTION_SHORT, PRICETYPE_MARKETPRICE)
priceTypeMapReverse = {v: k for k, v in priceTypeMap.items()}

# 印射字典
spotSymbolMap = {}
spotSymbolMap['LTCUSDT'] = LTC_USD_SPOT
spotSymbolMap['BTCUSDT'] = BTC_USD_SPOT
spotSymbolMap['ETHUSDT'] = ETH_USD_SPOT
spotSymbolMap['LTCBTC'] = LTC_BTC_SPOT
spotSymbolMap['ETHBTC'] = ETH_BTC_SPOT
spotSymbolMapReverse = {v: k for k, v in spotSymbolMap.items()}

# 委托状态印射
statusMap = {}
statusMap['CANCELED'] = STATUS_CANCELLED
statusMap['NEW'] = STATUS_NOTTRADED
statusMap['PARTIALLY_FILLED'] = STATUS_PARTTRADED
statusMap['FILLED'] = STATUS_ALLTRADED
statusMap['REJECTED'] = STATUS_REJECTED
statusMap['EXPIRED'] = STATUS_UNKNOWN
statusMap['PENDING_CANCEL'] = STATUS_UNKNOWN


class BinanceGateway(VtGateway):
    def __init__(self, eventEngine, gatewayName='Binance'):
        super(BinanceGateway, self).__init__(eventEngine, gatewayName)
        self.market = 'USDT'
        self.tradeApi = BinanceTradeApi(self)
        self.dataApi = BinanceDataApi(self)

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

        self.dataApi.connect(accessKey, secretKey, interval, market, debug)
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

    def subscribe(self, subscribeReq):
        """订阅行情"""
        self.dataApi.subscribe(subscribeReq.symbol)

    def sendOrder(self, orderReq):
        """发单"""
        self.tradeApi.sendOrder(orderReq)

    def cancelOrder(self, cancelOrderReq):
        """撤单"""
        self.tradeApi.cancel(cancelOrderReq)

    def qryAccount(self):
        """查询账户资金"""
        pass

    def qryPosition(self):
        """查询持仓"""
        pass

    def close(self):
        """关闭"""
        self.tradeApi.exit()
        self.dataApi.exit()

    def initQuery(self):
        """初始化连续查询"""
        if self.qryEnabled:
            self.qryFunctionList = [
                self.tradeApi.queryWorkingOrders, self.tradeApi.queryAccount
            ]
            self.startQuery()

    def query(self, event):
        """注册到事件处理引擎上的查询函数"""
        for function in self.qryFunctionList:
            function()

    def startQuery(self):
        """启动连续查询"""
        self.eventEngine.register(EVENT_TIMER, self.query)

    def setQryEnabled(self, qryEnabled):
        """设置是否要启动循环查询"""
        self.qryEnabled = qryEnabled


class BinanceTradeApi(vnbinance.BinanceApi):
    """交易接口"""

    def __init__(self, gateway):
        """Constructor"""
        super(BinanceTradeApi, self).__init__()

        self.gateway = gateway
        self.gatewayName = gateway.gatewayName

        self.subscribeSet = set()  # 订阅的币种

        self.localID = 0  # 本地委托号
        self.localSystemDict = {}  # key:localID, value:systemID
        self.systemLocalDict = {}  # key:systemID, value:localID
        self.workingOrderDict = {}  # key:localID, value:order
        self.reqLocalDict = {}  # key:reqID, value:localID
        self.cancelDict = {}  # key:localID, value:cancelOrderReq

        self.tradeID = 0  # 本地成交号

    def onError(self, error, req, reqID):
        """错误推送"""
        err = VtErrorData()
        err.gatewayName = self.gatewayName
        err.errorMsg = str(error)
        err.errorTime = datetime.now().strftime('%H:%M:%S')
        self.gateway.onError(err)

    def onGetAccountInfo(self, data, req, reqID):
        """查询账户回调"""
        # 推送账户数据
        balanceUsdt = 0.0
        for balance in data['balances']:
            symbol = balance['asset']
            if symbol == 'USDT':
                balanceUsdt = float(balance['free'])
            if symbol in [self.currency, self.symbolSet]:
                pos = VtPositionData()
                pos.gatewayName = self.gatewayName
                pos.symbol = symbol
                pos.vtSymbol = symbol
                pos.vtPositionName = symbol
                pos.direction = DIRECTION_NET
                pos.frozen = float(balance['locked'])
                pos.position = pos.frozen + float(balance['free'])
                self.gateway.onPosition(pos)

        account = VtAccountData()
        account.gatewayName = self.gatewayName
        account.accountID = self.gatewayName
        account.vtAccountID = account.accountID
        account.balance = balanceUsdt
        self.gateway.onAccount(account)

    def onGetOrders(self, data, req, reqID):
        """查询委托回调"""
        for d in data:
            order = VtOrderData()
            order.gatewayName = self.gatewayName

            # 合约代码
            order.symbol = d['symbol']
            order.exchange = EXCHANGE_BINANCE
            order.vtSymbol = order.symbol

            # 委托号
            systemID = d['orderId']
            self.localID += 1
            localID = str(self.localID)
            self.systemLocalDict[systemID] = localID
            self.localSystemDict[localID] = systemID
            order.orderID = localID
            order.vtOrderID = '.'.join([self.gatewayName, order.orderID])

            # 其他信息
            order.direction = priceTypeMap[d['side']]
            order.price = float(d['price'])
            order.totalVolume = float(d['origQty'])
            order.tradedVolume = float(d['executedQty'])
            order.orderTime = d['time']

            # 委托状态
            order.status = statusMap[d['status']]

            self.workingOrderDict[localID] = order
            self.gateway.onOrder(order)

    def onOrderInfo(self, data, req, reqID):
        """委托详情回调"""
        systemID = data['orderId']
        localID = self.systemLocalDict[systemID]
        order = self.workingOrderDict.get(localID, None)
        if not order:
            return

        # 记录最新成交的金额
        newTradeVolume = float(data['executedQty']) - order.tradedVolume
        if newTradeVolume:
            trade = VtTradeData()
            trade.gatewayName = self.gatewayName
            trade.symbol = order.symbol
            trade.vtSymbol = order.vtSymbol

            self.tradeID += 1
            trade.tradeID = str(self.tradeID)
            trade.vtTradeID = '.'.join([self.gatewayName, trade.tradeID])

            trade.volume = newTradeVolume
            trade.price = data['price']
            trade.direction = order.direction
            trade.offset = order.offset
            trade.exchange = order.exchange
            trade.tradeTime = datetime.now().strftime('%H:%M:%S')

            self.gateway.onTrade(trade)

        # 更新委托状态
        order.tradedVolume = float(data['executedQty'])
        order.status = statusMap[data['status']]

        if newTradeVolume:
            self.gateway.onOrder(order)

        if order.status == STATUS_ALLTRADED \
                or order.status == STATUS_CANCELLED:
            del self.workingOrderDict[order.orderID]

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

    def onCancelOrder(self, data, req, reqID):
        """撤单回调"""
        if data['orderId'] != '':
            systemID = req['params']['id']
            localID = self.systemLocalDict[systemID]

            order = self.workingOrderDict[localID]
            order.status = STATUS_CANCELLED

            del self.workingOrderDict[localID]
            self.gateway.onOrder(order)

    def connect(self, accessKey, secretKey, market, debug=False):
        """连接服务器"""
        self.market = market
        self.DEBUG = debug

        self.init(accessKey, secretKey)

        # 查询未成交委托
        self.getOrders()

    def subscribe(self, symbol):
        self.subscribeSet.add(symbol)

    def queryWorkingOrders(self):
        """查询活动委托状态"""
        for order in self.workingOrderDict.values():
            # 如果尚未返回委托号，则无法查询
            if order.orderID in self.localSystemDict:
                systemID = self.localSystemDict[order.orderID]
                symbol = order.symbol
                self.orderInfo(systemID, symbol)

    def queryAccount(self):
        """查询活动委托状态"""
        self.getAccountInfo()

    def sendOrder(self, req):
        """发送委托"""

        # 发送限价委托
        symbol = spotSymbolMapReverse[req.symbol]

        if req.direction == DIRECTION_LONG:
            reqID = self.buy(req.price, req.volume, symbol, market=self.market)
        else:
            reqID = self.sell(
                req.price, req.volume, symbol, market=self.market)

        self.localID += 1
        localID = str(self.localID)
        self.reqLocalDict[reqID] = localID

        # 推送委托信息
        order = VtOrderData()
        order.gatewayName = self.gatewayName

        order.symbol = req.symbol
        order.exchange = EXCHANGE_BINANCE
        order.vtSymbol = order.symbol
        order.orderID = localID
        order.vtOrderID = '.'.join([self.gatewayName, order.orderID])
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

    def cancel(self, req):
        """撤单"""
        localID = req.orderID
        if localID in self.localSystemDict:
            systemID = self.localSystemDict[localID]
            symbol = spotSymbolMapReverse[req.symbol]
            self.cancelOrder(systemID, symbol, self.market)
        else:
            self.cancelDict[localID] = req


class BinanceDataApi(vnbinance.DataApi):
    """行情接口"""

    def __init__(self, gateway):
        """Constructor"""
        super(BinanceDataApi, self).__init__()

        self.market = 'USDT'
        self.gateway = gateway
        self.gatewayName = gateway.gatewayName
        self.tickDict = {}  # key:symbol, value:tick

    def onTick(self, data):
        """实时成交推送"""
        print data

    def onDepth(self, data):
        """实时深度推送"""
        symbol = SYMBOL_MAP[data['symbol']]
        if symbol not in self.tickDict:
            tick = VtTickData()
            tick.gatewayName = self.gatewayName

            tick.symbol = symbol
            tick.exchange = EXCHANGE_BINANCE
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

    def subscribe(self, symbol):
        """订阅行情信息"""
        _symbol = spotSymbolMapReverse[symbol]
        self.subscribeDepth(_symbol)

        contract = VtContractData()
        contract.gatewayName = self.gatewayName
        contract.symbol = symbol
        contract.exchange = EXCHANGE_BINANCE
        contract.vtSymbol = '.'.join([contract.symbol, contract.exchange])
        contract.name = u'币币交易'
        contract.size = 1
        contract.priceTick = 0.000001
        contract.productClass = PRODUCT_SPOT
        self.gateway.onContract(contract)

    def connect(self, accessKey, secretKey, interval, market, debug=False):
        """连接服务器"""
        self.market = market
        self.init(accessKey, secretKey, interval, debug)
