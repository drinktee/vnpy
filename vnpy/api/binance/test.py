# encoding: UTF-8

from vnbinance import *
#
# # 在OkCoin网站申请这两个Key，分别对应用户名和密码
# apiKey = ''
# secretKey = ''
#
# # 创建API对象
api = DataApi()
api.subscribeTrade('ethbtc')
api.subscribeDepth('etcbtc')
api.subscribeDepth('ltcbtc')

sleep(5)
api.close()

# host = 'wss://stream.binance.com:9443/ws/ethbtc@depth'
# # 连接服务器，并等待1秒
# # api.connect(BINANCE_HOST, apiKey, secretKey, True)
# import websocket
#
# ws = websocket.create_connection("wss://stream.binance.com:9443/ws/ethbtc@depth")
# print ws.recv()

