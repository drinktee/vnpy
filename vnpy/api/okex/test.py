# encoding: UTF-8

from vnokex import *

# 在OkCoin网站申请这两个Key，分别对应用户名和密码
apiKey = ''
secretKey = ''

# 创建API对象
api = OkExApi()

# 连接服务器，并等待1秒
api.connect(OKEX_SPOT, apiKey, secretKey, True)

sleep(1)

# 测试登录
api.login()

# 测试现货行情API
#api.subscribeSpotTicker(SYMBOL_BTC_USDT)
#api.subscribeSpotDepth(SYMBOL_BTC_USDT, DEPTH_20)
#api.subscribeSpotKline(SYMBOL_BTC_USDT, INTERVAL_1M)
#api.subscribeSpotTradeData(SYMBOL_BTC_USDT)


# 测试现货交易API
api.subscribeSpotTrades(SYMBOL_LTC_USDT)
#api.subscribeSpotUserInfo(SYMBOL_BTC_USDT)
#api.spotUserInfo()

# 下单逻辑
api.spotTrade(SYMBOL_LTC_USDT, TYPE_BUY, 100, 0.01)

# 下单取消
# api.spotTrade(SYMBOL_ZEC_USDT, TYPE_BUY, 100, 0.01)
# api.spotCancelOrder(SYMBOL_ZEC_USDT, order_id)

# 测试期货行情API
# api.subscribeFutureTicker(SYMBOL_ETH_FUTURE, FUTURE_EXPIRY_THIS_WEEK)
# api.subscribeFutureDepth(SYMBOL_LTC_FUTURE, FUTURE_EXPIRY_QUARTER, DEPTH_20)
# api.subscribeFutureKline(SYMBOL_BTC_FUTURE, FUTURE_EXPIRY_THIS_WEEK, INTERVAL_1M)
# api.subscribeFutureIndex(SYMBOL_BTC_FUTURE)
# api.subscribeFutureTradeData(SYMBOL_BTC_FUTURE, FUTURE_EXPIRY_THIS_WEEK)

# 测试期货交易API
#api.subscribeFutureTrades()
#api.subscribeFutureUserInfo()
#api.subscribeFuturePositions()
#api.futureUserInfo()
#api.futureTrade(symbol, expiry, type_, price, amount, order, leverage)
#api.futureCancelOrder(symbol, expiry, orderid)
#api.futureOrderInfo(symbol, expiry, orderid, status, page, length)
#api.subscribeFutureUserInfo()
#api.subscribeFutureTrades()


raw_input()