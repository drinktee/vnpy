# encoding: UTF-8

'''
vn.okcoin的gateway接入

注意：
1. 前仅支持USD和CNY的现货交易，USD的期货合约交易暂不支持
'''


import os
import json
from datetime import datetime
from time import sleep
from copy import copy
from threading import Condition
from Queue import Queue
from threading import Thread
import time

from vnpy.api.okex import vnokex
from vnpy.api.okex.vnokex import *
from vnpy.trader.vtGateway import *
from vnpy.trader.vtFunction import getJsonPath

# 价格类型映射
priceTypeMap = {}
priceTypeMap['buy'] = (DIRECTION_LONG, PRICETYPE_LIMITPRICE)
priceTypeMap['buy_market'] = (DIRECTION_LONG, PRICETYPE_MARKETPRICE)
priceTypeMap['sell'] = (DIRECTION_SHORT, PRICETYPE_LIMITPRICE)
priceTypeMap['sell_market'] = (DIRECTION_SHORT, PRICETYPE_MARKETPRICE)
priceTypeMapReverse = {v: k for k, v in priceTypeMap.items()} 

# 方向类型映射
directionMap = {}
directionMapReverse = {v: k for k, v in directionMap.items()}

# 委托状态印射
statusMap = {}
statusMap[-1] = STATUS_CANCELLED
statusMap[0] = STATUS_NOTTRADED
statusMap[1] = STATUS_PARTTRADED
statusMap[2] = STATUS_ALLTRADED
statusMap[4] = STATUS_UNKNOWN

############################################
## 交易合约代码
############################################

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

# 印射字典
spotSymbolMap = {}
spotSymbolMap['ltc_usdt'] = LTC_USD_SPOT
spotSymbolMap['btc_usdt'] = BTC_USD_SPOT
spotSymbolMap['eth_usdt'] = ETH_USD_SPOT
spotSymbolMap['ltc_btc'] = LTC_BTC_SPOT
spotSymbolMap['eth_btc'] = ETH_BTC_SPOT
spotSymbolMapReverse = {v: k for k, v in spotSymbolMap.items()}


############################################
## Channel和Symbol的印射
############################################
channelSymbolMap = {}

# USD
# ok_sub_spot_%s_ticker

channelSymbolMap['ok_sub_spot_btc_usdt_ticker'] = BTC_USD_SPOT
channelSymbolMap['ok_sub_spot_ltc_usdt_ticker'] = LTC_USD_SPOT
channelSymbolMap['ok_sub_spot_eth_usdt_ticker'] = ETH_USD_SPOT

channelSymbolMap['ok_sub_spot_btc_usdt_depth_20'] = BTC_USD_SPOT
channelSymbolMap['ok_sub_spot_ltc_usdt_depth_20'] = LTC_USD_SPOT
channelSymbolMap['ok_sub_spot_eth_usdt_depth_20'] = ETH_USD_SPOT

# BTC
channelSymbolMap['ok_sub_spot_ltc_btc_ticker'] = LTC_BTC_SPOT
channelSymbolMap['ok_sub_spot_eth_btc_ticker'] = ETH_BTC_SPOT

channelSymbolMap['ok_sub_spot_ltc_btc_depth_20'] = LTC_BTC_SPOT
channelSymbolMap['ok_sub_spot_eth_btc_depth_20'] = ETH_BTC_SPOT


############################################
## funds和Symbol的印射
############################################
fundsSymbolMap = {}
fundsSymbolMap[ETH_BTC_SPOT] = 'eth'
fundsSymbolMap[ETH_USD_SPOT] = 'eth'
fundsSymbolMap[LTC_BTC_SPOT] = 'ltc'
fundsSymbolMap[LTC_USD_SPOT] = 'ltc'
fundsSymbolMap[BTC_USD_SPOT] = 'btc'


########################################################################
class OkexGateway(VtGateway):
    """OkCoin接口"""

    #----------------------------------------------------------------------
    def __init__(self, eventEngine, gatewayName='OKEX'):
        """Constructor"""
        super(OkexGateway, self).__init__(eventEngine, gatewayName)
        
        self.api = Api(self)     
        
        self.leverage = 0
        self.connected = False

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
            host = str(setting['host'])
            apiKey = str(setting['apiKey'])
            secretKey = str(setting['secretKey'])
            trace = setting['trace']
            leverage = setting['leverage']
        except KeyError:
            log = VtLogData()
            log.gatewayName = self.gatewayName
            log.logContent = u'连接配置缺少字段，请检查'
            self.onLog(log)
            return            


        # 初始化接口
        self.leverage = leverage
        self.api.active = True
        self.api.connect(host, apiKey, secretKey, trace)
        
        log = VtLogData()
        log.gatewayName = self.gatewayName
        log.logContent = u'接口初始化成功'
        self.onLog(log)
        
        # 启动查询
        self.initQuery()
        self.startQuery()



    
    #----------------------------------------------------------------------
    def subscribe(self, subscribeReq):
        """订阅行情"""
        self.api.subscribe(subscribeReq)
        
    #----------------------------------------------------------------------
    def sendOrder(self, orderReq):
        """发单"""
        return self.api.spotSendOrder(orderReq)
        
    #----------------------------------------------------------------------
    def cancelOrder(self, cancelOrderReq):
        """撤单"""
        self.api.spotCancel(cancelOrderReq)
        
    #----------------------------------------------------------------------
    def qryAccount(self):
        """查询账户资金"""
        self.api.spotUserInfo()
        
    #----------------------------------------------------------------------
    def qryPosition(self):
        """查询持仓"""
        pass
        
    #----------------------------------------------------------------------
    def close(self):
        """关闭"""
        self.api.active = False
        self.api.close()
        
    #----------------------------------------------------------------------
    def initQuery(self):
        """初始化连续查询"""
        if self.qryEnabled:
            # 需要循环的查询函数列表
            self.qryFunctionList = [self.qryAccount]
            
            self.qryCount = 0           # 查询触发倒计时
            self.qryTrigger = 2         # 查询触发点
            self.qryNextFunction = 0    # 上次运行的查询函数索引
            
            self.startQuery()  
    
    #----------------------------------------------------------------------
    def query(self, event):
        """注册到事件处理引擎上的查询函数"""
        self.qryCount += 1
        
        if self.qryCount > self.qryTrigger:
            # 清空倒计时
            self.qryCount = 0
            
            # 执行查询函数
            function = self.qryFunctionList[self.qryNextFunction]
            function()
            
            # 计算下次查询函数的索引，如果超过了列表长度，则重新设为0
            self.qryNextFunction += 1
            if self.qryNextFunction == len(self.qryFunctionList):
                self.qryNextFunction = 0
                
    #----------------------------------------------------------------------
    def startQuery(self):
        """启动连续查询"""
        self.eventEngine.register(EVENT_TIMER, self.query)
    
    #----------------------------------------------------------------------
    def setQryEnabled(self, qryEnabled):
        """设置是否要启动循环查询"""
        self.qryEnabled = qryEnabled


########################################################################
class Api(vnokex.OkExApi):
    """OkCoin的API实现"""

    #----------------------------------------------------------------------
    def __init__(self, gateway):
        """Constructor"""
        super(Api, self).__init__()
        
        self.gateway = gateway                  # gateway对象
        self.gatewayName = gateway.gatewayName  # gateway对象名称
        self.exchange = EXCHANGE_OKEX

        self.active = False             # 若为True则会在断线后自动重连
        self.subscribedSymbols = set()  # 已经订阅的产品

        self.symbolSet = set()
        self.cbDict = {}
        self.tickDict = {}
        self.orderDict = {}
        
        self.localNo = 0                # 本地委托号
        self.localNoQueue = Queue()     # 未收到系统委托号的本地委托号队列
        self.localNoDict = {}           # key为本地委托号，value为系统委托号
        self.orderIdDict = {}           # key为系统委托号，value为本地委托号
        self.cancelDict = {}            # key为本地委托号，value为撤单请求
        
        self.initCallback()
        
    #----------------------------------------------------------------------
    def onMessage(self, ws, evt):
        """信息推送""" 
        data = self.readData(evt)[0]
        channel = data['channel']
        if channel in self.cbDict:
            callback = self.cbDict[channel]
            callback(data)
        
    #----------------------------------------------------------------------
    def onError(self, ws, evt):
        """错误推送"""
        error = VtErrorData()
        error.gatewayName = self.gatewayName
        error.errorMsg = str(evt)
        self.gateway.onError(error)
        
    #----------------------------------------------------------------------
    def onClose(self, ws):
        """接口断开"""
        # 如果尚未连上，则忽略该次断开提示
        if not self.gateway.connected:
            return
        
        self.gateway.connected = False
        self.writeLog(u'服务器连接断开')
        
        # 重新连接
        if self.active:
            
            def reconnect():
                while not self.gateway.connected:            
                    self.writeLog(u'等待10秒后重新连接')
                    sleep(10)
                    if not self.gateway.connected:
                        self.reconnect()
            
            t = Thread(target=reconnect)
            t.start()
        
    #----------------------------------------------------------------------
    def onOpen(self, ws):       
        """连接成功"""
        self.gateway.connected = True
        self.writeLog(u'服务器连接成功')
        
        # 连接后查询账户和委托数据
        self.login()
        self.spotUserInfo()

        for subscribeReq in self.subscribedSymbols:
            symbol = subscribeReq.symbol
            self.subscribeSpotDepth(spotSymbolMapReverse[symbol], DEPTH_20)
            self.symbolSet.add(fundsSymbolMap[symbol])
            self.cbDict['ok_sub_spot_%s_ticker' % (spotSymbolMapReverse[symbol])] = self.onTicker
            self.cbDict['ok_sub_spot_%s_depth_20' % (spotSymbolMapReverse[symbol])] = self.onDepth
            self.cbDict['ok_spot_%s_balance' % (spotSymbolMapReverse[symbol])] = self.onSpotSubUserInfo
            self.cbDict['ok_spot_%s_order' % (spotSymbolMapReverse[symbol])] = self.onSpotSubTrades
            self.writeLog(u'订阅合约 %s 成功' % symbol)

    #----------------------------------------------------------------------
    def writeLog(self, content):
        """快速记录日志"""
        log = VtLogData()
        log.gatewayName = self.gatewayName
        log.logContent = content
        self.gateway.onLog(log)

    def subscribe(self, subscribeReq):
        """订阅行情信息"""
        if self.gateway.connected:
            symbol = subscribeReq.symbol
            self.subscribeSpotDepth(spotSymbolMapReverse[symbol], DEPTH_20)
            self.symbolSet.add(fundsSymbolMap[symbol])
            self.cbDict['ok_sub_spot_%s_ticker' % (spotSymbolMapReverse[symbol])] = self.onTicker
            self.cbDict['ok_sub_spot_%s_depth_20' % (spotSymbolMapReverse[symbol])] = self.onDepth
            self.cbDict['ok_spot_%s_balance' % (spotSymbolMapReverse[symbol])] = self.onSpotSubUserInfo
            self.cbDict['ok_spot_%s_order' % (spotSymbolMapReverse[symbol])] = self.onSpotSubTrades
            self.writeLog(u'订阅合约 %s 成功' % symbol)
        self.subscribedSymbols.add(subscribeReq)


    #---------------------------------------------------------------------
    def initCallback(self):
        """初始化回调函数"""
        # USD_SPOT
        self.cbDict['ok_spot_userinfo'] = self.onSpotUserInfo
        self.cbDict['ok_spot_orderinfo'] = self.onSpotOrderInfo

        self.cbDict['ok_spot_order'] = self.onSpotTrade
        self.cbDict['ok_spot_cancel_order'] = self.onSpotCancelOrder

    #----------------------------------------------------------------------
    def onTicker(self, data):
        """"""
        if 'data' not in data:
            return
        
        channel = data['channel']
        symbol = channelSymbolMap[channel]
        
        if symbol not in self.tickDict:
            tick = VtTickData()
            tick.symbol = symbol
            tick.vtSymbol = '.'.join([symbol, self.exchange])
            tick.gatewayName = self.gatewayName
            self.tickDict[symbol] = tick
        else:
            tick = self.tickDict[symbol]
        
        rawData = data['data']
        tick.highPrice = float(rawData['high'])
        tick.lowPrice = float(rawData['low'])
        tick.lastPrice = float(rawData['last'])
        tick.volume = float(rawData['vol'])
        tick.date, tick.time = generateDateTime(rawData['timestamp'])
        
        newtick = copy(tick)
        self.gateway.onTick(newtick)
    
    #----------------------------------------------------------------------
    def onDepth(self, data):
        """"""
        if 'data' not in data:
            return
        
        channel = data['channel']
        symbol = channelSymbolMap[channel]
        
        if symbol not in self.tickDict:
            tick = VtTickData()
            tick.symbol = symbol
            tick.vtSymbol = '.'.join([symbol, self.exchange])
            tick.gatewayName = self.gatewayName
            self.tickDict[symbol] = tick
        else:
            tick = self.tickDict[symbol]
        
        if 'data' not in data:
            return
        rawData = data['data']
        
        tick.bidPrice1, tick.bidVolume1 = rawData['bids'][0]
        tick.bidPrice2, tick.bidVolume2 = rawData['bids'][1]
        tick.bidPrice3, tick.bidVolume3 = rawData['bids'][2]
        tick.bidPrice4, tick.bidVolume4 = rawData['bids'][3]
        tick.bidPrice5, tick.bidVolume5 = rawData['bids'][4]
        
        tick.askPrice1, tick.askVolume1 = rawData['asks'][-1]
        tick.askPrice2, tick.askVolume2 = rawData['asks'][-2]
        tick.askPrice3, tick.askVolume3 = rawData['asks'][-3]
        tick.askPrice4, tick.askVolume4 = rawData['asks'][-4]
        tick.askPrice5, tick.askVolume5 = rawData['asks'][-5]     
        
        tick.date, tick.time = generateDateTime(rawData['timestamp'])
        
        newtick = copy(tick)
        self.gateway.onTick(newtick)
    
    #----------------------------------------------------------------------
    def onSpotUserInfo(self, data):
        """现货账户资金推送"""
        rawData = data['data']
        info = rawData['info']
        funds = rawData['info']['funds']


        for symbol in [self.currency, self.symbolSet]:
            if symbol in funds['free'].keys():
                pos = VtPositionData()
                pos.gatewayName = self.gatewayName

                pos.symbol = symbol
                pos.vtSymbol = '.'.join([symbol, self.exchange])
                pos.vtPositionName = symbol
                pos.direction = DIRECTION_NET

                pos.frozen = float(funds['freezed'][symbol])
                pos.position = pos.frozen + float(funds['free'][symbol])

                self.gateway.onPosition(pos)

        # 账户资金
        account = VtAccountData()
        account.gatewayName = self.gatewayName
        account.accountID = self.gatewayName
        account.vtAccountID = account.accountID
        account.balance = float(funds['free']['usdt'])
        self.gateway.onAccount(account)

    #----------------------------------------------------------------------
    def onSpotSubUserInfo(self, data):
        """现货账户资金推送"""
        if 'data' not in data:
            return
        
        rawData = data['data']
        info = rawData['info']
        
        # 持仓信息
        for symbol in [self.currency, self.symbolSet]:
            if symbol in info['free']:
                pos = VtPositionData()
                pos.gatewayName = self.gatewayName
                
                pos.symbol = symbol
                pos.vtSymbol = '.'.join([symbol, self.exchange])
                pos.vtPositionName = symbol
                pos.direction = DIRECTION_NET
                
                pos.frozen = float(info['freezed'][symbol])
                pos.position = pos.frozen + float(info['free'][symbol])
                
                self.gateway.onPosition(pos)  
                
    #----------------------------------------------------------------------
    def onSpotSubTrades(self, data):
        """成交和委托推送"""
        if 'data' not in data:
            return
        rawData = data['data']
        
        # 本地和系统委托号
        orderId = str(rawData['orderId'])
        localNo = self.orderIdDict[orderId]
        
        # 委托信息
        if orderId not in self.orderDict:
            order = VtOrderData()
            order.gatewayName = self.gatewayName
            
            order.symbol = spotSymbolMap[rawData['symbol']]
            order.vtSymbol = '.'.join([order.symbol, self.exchange])
    
            order.orderID = localNo
            order.vtOrderID = '.'.join([self.gatewayName, order.orderID])
            
            order.price = float(rawData['tradeUnitPrice'])
            order.totalVolume = float(rawData['tradeAmount'])
            order.direction, priceType = priceTypeMap[rawData['tradeType']]    
            
            self.orderDict[orderId] = order
        else:
            order = self.orderDict[orderId]
            
        order.tradedVolume = float(rawData['completedTradeAmount'])
        order.status = statusMap[rawData['status']]
        
        self.gateway.onOrder(copy(order))
        
        # 成交信息
        if 'sigTradeAmount' in rawData and float(rawData['sigTradeAmount'])>0:
            trade = VtTradeData()
            trade.gatewayName = self.gatewayName
            
            trade.symbol = spotSymbolMap[rawData['symbol']]
            trade.vtSymbol = '.'.join([order.symbol, self.exchange])
            
            trade.tradeID = str(rawData['id'])
            trade.vtTradeID = '.'.join([self.gatewayName, trade.tradeID])
            
            trade.orderID = localNo
            trade.vtOrderID = '.'.join([self.gatewayName, trade.orderID])
            
            trade.price = float(rawData['sigTradePrice'])
            trade.volume = float(rawData['sigTradeAmount'])
            
            trade.direction, priceType = priceTypeMap[rawData['tradeType']]    
            
            trade.tradeTime = datetime.now().strftime('%H:%M:%S')
            
            self.gateway.onTrade(trade)
        
    #----------------------------------------------------------------------
    def onSpotOrderInfo(self, data):
        """委托信息查询回调"""
        rawData = data['data']
        
        for d in rawData['orders']:
            self.localNo += 1
            localNo = str(self.localNo)
            orderId = str(d['order_id'])
            
            self.localNoDict[localNo] = orderId
            self.orderIdDict[orderId] = localNo
            
            if orderId not in self.orderDict:
                order = VtOrderData()
                order.gatewayName = self.gatewayName
                
                order.symbol = spotSymbolMap[d['symbol']]
                order.vtSymbol = '.'.join([order.symbol, self.exchange])
    
                order.orderID = localNo
                order.vtOrderID = '.'.join([self.gatewayName, order.orderID])
                
                order.price = d['price']
                order.totalVolume = d['amount']
                order.direction, priceType = priceTypeMap[d['type']]
                
                self.orderDict[orderId] = order
            else:
                order = self.orderDict[orderId]
                
            order.tradedVolume = d['deal_amount']
            order.status = statusMap[d['status']]            
            
            self.gateway.onOrder(copy(order))
    
    #----------------------------------------------------------------------
    def generateSpecificContract(self, contract, symbol):
        """生成合约"""
        new = copy(contract)
        new.symbol = symbol
        new.vtSymbol = '.'.join([new.symbol, self.exchange])
        new.name = symbol
        return new

    #----------------------------------------------------------------------
    def generateUsdContract(self):
        """生成USD合约信息"""
        contractList = []
        
        # 现货
        contract = VtContractData()
        contract.exchange = EXCHANGE_OKCOIN
        contract.productClass = PRODUCT_SPOT
        contract.size = 1
        contract.priceTick = 0.01
        
        contractList.append(self.generateSpecificContract(contract, BTC_USD_SPOT))
        contractList.append(self.generateSpecificContract(contract, LTC_USD_SPOT))
        contractList.append(self.generateSpecificContract(contract, ETH_USD_SPOT))

        # 期货
        contract.productClass = PRODUCT_FUTURES
        
        contractList.append(self.generateSpecificContract(contract, BTC_USD_THISWEEK))
        contractList.append(self.generateSpecificContract(contract, BTC_USD_NEXTWEEK))
        contractList.append(self.generateSpecificContract(contract, BTC_USD_QUARTER))
        contractList.append(self.generateSpecificContract(contract, LTC_USD_THISWEEK))
        contractList.append(self.generateSpecificContract(contract, LTC_USD_NEXTWEEK))
        contractList.append(self.generateSpecificContract(contract, LTC_USD_QUARTER))
        contractList.append(self.generateSpecificContract(contract, ETH_USD_THISWEEK))
        contractList.append(self.generateSpecificContract(contract, ETH_USD_NEXTWEEK))
        contractList.append(self.generateSpecificContract(contract, ETH_USD_QUARTER))
        
        return contractList        
    
    #----------------------------------------------------------------------
    def onSpotTrade(self, data):
        """委托回报"""
        rawData = data['data']
        orderId = rawData['order_id']
        
        # 尽管websocket接口的委托号返回是异步的，但经过测试是
        # 符合先发现回的规律，因此这里通过queue获取之前发送的
        # 本地委托号，并把它和推送的系统委托号进行映射
        localNo = self.localNoQueue.get_nowait()
        
        self.localNoDict[localNo] = orderId
        self.orderIdDict[orderId] = localNo
        
        # 检查是否有系统委托号返回前就发出的撤单请求，若有则进
        # 行撤单操作
        if localNo in self.cancelDict:
            req = self.cancelDict[localNo]
            self.spotCancel(req)
            del self.cancelDict[localNo]
    
    #----------------------------------------------------------------------
    def onSpotCancelOrder(self, data):
        """撤单回报"""
        pass
    
    #----------------------------------------------------------------------
    def spotSendOrder(self, req):
        """发单"""
        symbol = spotSymbolMapReverse[req.symbol]
        type_ = priceTypeMapReverse[(req.direction, req.priceType)]
        self.spotTrade(symbol, type_, str(req.price), str(req.volume))
        
        # 本地委托号加1，并将对应字符串保存到队列中，返回基于本地委托号的vtOrderID
        self.localNo += 1
        self.localNoQueue.put(str(self.localNo))
        vtOrderID = '.'.join([self.gatewayName, str(self.localNo)])
        return vtOrderID
    
    #----------------------------------------------------------------------
    def spotCancel(self, req):
        """撤单"""
        symbol = spotSymbolMapReverse[req.symbol][:4]
        localNo = req.orderID
        
        if localNo in self.localNoDict:
            orderID = self.localNoDict[localNo]
            self.spotCancelOrder(symbol, orderID)
        else:
            # 如果在系统委托号返回前客户就发送了撤单请求，则保存
            # 在cancelDict字典中，等待返回后执行撤单任务
            self.cancelDict[localNo] = req
    
#----------------------------------------------------------------------
def generateDateTime(s):
    """生成时间"""
    dt = datetime.fromtimestamp(float(s)/1e3)
    time = dt.strftime("%H:%M:%S.%f")
    date = dt.strftime("%Y%m%d")
    return date, time