# encoding: UTF-8

from vnbinance import *
#
# # 在OkCoin网站申请这两个Key，分别对应用户名和密码
apiKey = 'YWPMXH4EUBVbIS0TGIj3mLhJ1Ezzp0ZxBxKCSnKLx5CTm7hpmTWJDTiT4UeLZ2sZ'
secretKey = '8gySF1Ex8TeQExSwJPVpdOvJytqVMqH2a1fenQ0KnFUI2wORBzA8gsfiyEPUXaG3'
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
api.getAccountInfo()

input()