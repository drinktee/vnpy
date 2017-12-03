# encoding: UTF-8

from vnbinance import *
#
# # 在OkCoin网站申请这两个Key，分别对应用户名和密码
apiKey = ''
secretKey = ''
#
# # 创建API对象
#api = DataApi()
#api.subscribeTrade('ethbtc')
#api.subscribeDepth('etcbtc')
#api.subscribeDepth('ltcbtc')

#sleep(5)
#api.close()

api = TradeApi()
api.init(apiKey, secretKey)
#api.getDepth(SYMBOL_LTC_BTC)
#api.getKline(SYMBOL_LTC_BTC)
#api.getAccountInfo()
api.trade(SYMBOL_LTC_BTC, ORDER_SIDE_BUY, ORDER_TYPE_LIMIT, 0.01, 100, True)

input()