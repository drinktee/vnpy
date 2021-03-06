# encoding: utf-8

from vnhuobi import *

#----------------------------------------------------------------------
def testTrade():
    """测试交易"""
    accessKey = ''
    secretKey = ''
    
    # 创建API对象并初始化
    api = TradeApi()
    api.DEBUG = True
    api.init(accessKey, secretKey)
    
    # 查询账户，测试通过
    api.getAccountInfo()
    sleep(2)
    api.getBalance()
    
    # 查询委托，测试通过
    #api.getOrders()
    
    # 买入，测试通过
    # api.buy(1, 0.001, SYMBOL_BTCUSDT)
    api.cancelOrder("450067754")
    
    # 卖出，测试通过
    #api.sell(7120, 0.0095)
    
    # 撤单，测试通过
    #api.cancelOrder(3915047376L)
    
    # 查询杠杆额度，测试通过
    #api.getLoanAvailable()
    
    # 查询杠杆列表，测试通过
    #api.getLoans()
 
    # 阻塞
    input()    


#----------------------------------------------------------------------
def testData():
    """测试行情接口"""
    api = DataApi()
    
    api.init(0.5, True)
    
    # 订阅成交推送，测试通过
    api.subscribeTick(SYMBOL_ETHBTC)

    api.subscribeDepth(SYMBOL_ETHBTC)

    # 查询K线数据，测试通过
    data = api.getKline(SYMBOL_ETHBTC, PERIOD_1MIN)
    print data
    
    input()


def testDataWebsocket():
    accessKey = ''
    secretKey = ''
    api = DataWebSocketApi()
    api.connect(HUOBI_WEBSOCKET_WSS, accessKey, secretKey)
    sleep(5)
    api.sendDepthDataRequest(SYMBOL_ETHBTC, DEPTH_STEP0)

if __name__ == '__main__':
    testTrade()
    #testData()
    #testDataWebsocket()
