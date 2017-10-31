# encoding: utf-8
__author__ = 'foursking'


from vntushare import *

SYMBOL = "000581"

#----------------------------------------------------------------------
def testData():
    """测试行情接口"""
    api = DataApi()

    api.init(1, True)

    # 订阅成交推送，测试通过
    data = api.subscribeTick(SYMBOL)

    # 订阅报价推送，测试通过
    #api.subscribeQuote(SYMBOL_BTCCNY)

    # 订阅深度推送，测试通过
    # data = api.subscribeDepth(SYMBOL, 1)

    # 查询K线数据，测试通过
    #data = api.getKline(SYMBOL_BTCCNY, PERIOD_1MIN, 100)
    #print data

    input()


if __name__ == '__main__':
    #testTrade()

    testData()