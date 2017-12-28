# encoding: utf-8
import traceback

from time import sleep
from Queue import Queue, Empty
from threading import Thread
from binance.client import Client

# 常量定义
COINTYPE_BTC = 1
COINTYPE_LTC = 2

ACCOUNTTYPE_CNY = 1
ACCOUNTTYPE_USD = 2

LOANTYPE_CNY = 1
LOANTYPE_BTC = 2
LOANTYPE_LTC = 3
LOANTYPE_USD = 4

MARKETTYPE_CNY = 'cny'
MARKETTYPE_USD = 'usd'

SYMBOL_ETHUSD = 'ETHUSDT'
SYMBOL_LTCUSD = 'LTCUSDT'
SYMBOL_BTCUSD = 'BTCUSDT'

# 功能代码
FUNCTIONCODE_GETACCOUNTINFO = 'get_account_info'
FUNCTIONCODE_GETORDERS = 'get_orders'
FUNCTIONCODE_ORDERINFO = 'order_info'
FUNCTIONCODE_BUY = 'buy'
FUNCTIONCODE_SELL = 'sell'
FUNCTIONCODE_BUYMARKET = 'buy_market'
FUNCTIONCODE_SELLMARKET = 'sell_market'
FUNCTIONCODE_CANCELORDER = 'cancel_order'
FUNCTIONCODE_GETNEWDEALORDERS = 'get_new_deal_orders'
FUNCTIONCODE_GETORDERIDBYTRADEID = 'get_order_id_by_trade_id'
FUNCTIONCODE_WITHDRAWCOIN = 'withdraw_coin'
FUNCTIONCODE_CANCELWITHDRAWCOIN = 'cancel_withdraw_coin'
FUNCTIONCODE_GETWITHDRAWCOINRESULT = 'get_withdraw_coin_result'
FUNCTIONCODE_TRANSFER = 'transfer'
FUNCTIONCODE_LOAN = 'loan'
FUNCTIONCODE_REPAYMENT = 'repayment'
FUNCTIONCODE_GETLOANAVAILABLE = 'get_loan_available'
FUNCTIONCODE_GETLOANS = 'get_loans'


class BinanceApi(object):
    """交易接口"""
    DEBUG = True

    def __init__(self):
        """Constructor"""
        self.accessKey = ''
        self.secretKey = ''
        self.currency = {'USDT', 'BTC', 'ETH'}
        self.symbolSet = set()
        self.client = Client('', '')
        self.active = False  # API工作状态   
        self.reqID = 0  # 请求编号
        self.reqQueue = Queue()  # 请求队列
        self.reqThread = Thread(target=self.processQueue)  # 请求处理线程       

    def processRequest(self, req):
        """处理请求"""
        # 读取方法和参数
        method = req['method']
        reqID = req['reqID']
        params = req['params']
        # 发送请求

        # 查询委托
        if method == FUNCTIONCODE_GETORDERS:
            try:
                symbol = params['symbol']
                if symbol != '':
                    r = self.client.get_open_orders(symbol)
                else:
                    r = self.client.get_open_orders()
                return r.json()
            except Exception as err:
                self.onError(err, req, reqID)
                return None

        # 查询账户
        if method == FUNCTIONCODE_GETACCOUNTINFO:
            try:
                r = self.client.get_account()
                return r.json()
            except Exception as err:
                self.onError(err, req, reqID)
                return None

        # 获取委托详情
        if method == FUNCTIONCODE_ORDERINFO:
            try:
                symbol = params['symbol']
                orderid = params['id']
                r = self.client.get_order(symbol, orderid)
                return r.json()
            except Exception as err:
                self.onError(err, req, reqID)
                return None

        # 撤销委托
        if method == FUNCTIONCODE_CANCELORDER:
            try:
                symbol = params['symbol']
                orderid = params['id']
                r = self.client.cancel_order(symbol, orderid)
                return r.json()
            except Exception as err:
                self.onError(err, req, reqID)
                return None

        # 委托买入
        if method == FUNCTIONCODE_BUY:
            try:
                symbol = params['symbol']
                price = params['price']
                amount = params['amount']
                r = self.client.order_limit_buy(symbol, amount, price)
                return r.json()
            except Exception as err:
                self.onError(err, req, reqID)
                return None

        # 委托卖出
        if method == FUNCTIONCODE_SELL:
            try:
                symbol = params['symbol']
                price = params['price']
                amount = params['amount']
                r = self.client.order_limit_sell(symbol, amount, price)
                return r.json()
            except Exception as err:
                self.onError(err, req, reqID)
                return None

    def processQueue(self):
        """处理请求队列中的请求"""
        while self.active:
            try:
                req = self.reqQueue.get(block=True, timeout=1)  # 获取请求的阻塞为一秒
                callback = req['callback']
                reqID = req['reqID']

                data = self.processRequest(req)
                # 请求成功
                if data is not None:
                    if self.DEBUG:
                        print(callback.__name__)
                    callback(data, req, reqID)
            except Empty:
                pass

    def sendRequest(self, method, params, callback, optional=None):
        """发送请求"""
        # 请求编号加1
        self.reqID += 1

        # 生成请求字典并放入队列中
        req = {}
        req['method'] = method
        req['params'] = params
        req['callback'] = callback
        req['optional'] = optional
        req['reqID'] = self.reqID
        self.reqQueue.put(req)

        # 返回请求编号
        return self.reqID

    def init(self, accessKey, secretKey):
        """初始化"""
        self.accessKey = accessKey
        self.secretKey = secretKey
        self.client = Client(accessKey, secretKey)
        self.active = True
        self.reqThread.start()

    def exit(self):
        """退出"""
        self.active = False

        if self.reqThread.isAlive():
            self.reqThread.join()

    def getAccountInfo(self, market='USDT'):
        """查询账户"""
        method = FUNCTIONCODE_GETACCOUNTINFO
        params = {}
        callback = self.onGetAccountInfo
        optional = {'market': market}
        return self.sendRequest(method, params, callback, optional)

    def getOrders(self, symbol='', market='USDT'):
        """查询委托"""
        method = FUNCTIONCODE_GETORDERS
        params = {'symbol': symbol}
        callback = self.onGetOrders
        optional = {'market': market}
        return self.sendRequest(method, params, callback, optional)

    def orderInfo(self, id_, symbol='', market='USDT'):
        """获取委托详情"""
        method = FUNCTIONCODE_ORDERINFO
        params = {'symbol': symbol, 'id': id_}
        callback = self.onOrderInfo
        optional = {'market': market}
        return self.sendRequest(method, params, callback, optional)

    def buy(self,
            price,
            amount,
            symbol='',
            tradePassword='',
            tradeId='',
            market='USDT'):
        """委托买入"""
        method = FUNCTIONCODE_BUY
        params = {'symbol': symbol, 'price': price, 'amount': amount}
        callback = self.onBuy
        optional = {
            'trade_password': tradePassword,
            'trade_id': tradeId,
            'market': market
        }
        return self.sendRequest(method, params, callback, optional)

    def sell(self,
             price,
             amount,
             symbol='',
             tradePassword='',
             tradeId='',
             market='cny'):
        """委托卖出"""
        method = FUNCTIONCODE_SELL
        params = {'symbol': symbol, 'price': price, 'amount': amount}
        callback = self.onSell
        optional = {
            'trade_password': tradePassword,
            'trade_id': tradeId,
            'market': market
        }
        return self.sendRequest(method, params, callback, optional)

    def buyMarket(self,
                  amount,
                  coinType=COINTYPE_BTC,
                  tradePassword='',
                  tradeId='',
                  market='cny'):
        """市价买入"""
        method = FUNCTIONCODE_BUYMARKET
        params = {'coin_type': coinType, 'amount': amount}
        callback = self.onBuyMarket
        optional = {
            'trade_password': tradePassword,
            'trade_id': tradeId,
            'market': market
        }
        return self.sendRequest(method, params, callback, optional)

    def sellMarket(self,
                   amount,
                   coinType=COINTYPE_BTC,
                   tradePassword='',
                   tradeId='',
                   market='cny'):
        """市价卖出"""
        method = FUNCTIONCODE_SELLMARKET
        params = {'coin_type': coinType, 'amount': amount}
        callback = self.onSellMarket
        optional = {
            'trade_password': tradePassword,
            'trade_id': tradeId,
            'market': market
        }
        return self.sendRequest(method, params, callback, optional)

    def cancelOrder(self, id_, symbol='', market='USDT'):
        """撤销委托"""
        method = FUNCTIONCODE_CANCELORDER
        params = {'symbol': symbol, 'id': id_}
        callback = self.onCancelOrder
        optional = {'market': market}
        return self.sendRequest(method, params, callback, optional)

    def getNewDealOrders(self, market='cny'):
        """查询最新10条成交"""
        method = FUNCTIONCODE_GETNEWDEALORDERS
        params = {}
        callback = self.onGetNewDealOrders
        optional = {'market': market}
        return self.sendRequest(method, params, callback, optional)

    def getOrderIdByTradeId(self, tradeId, coinType=COINTYPE_BTC,
                            market='cny'):
        """通过成交编号查询委托编号"""
        method = FUNCTIONCODE_GETORDERIDBYTRADEID
        params = {'coin_type': coinType, 'trade_id': tradeId}
        callback = self.onGetOrderIdByTradeId
        optional = {'market': market}
        return self.sendRequest(method, params, callback, optional)

    def withdrawCoin(self,
                     withdrawAddress,
                     withdrawAmount,
                     coinType=COINTYPE_BTC,
                     tradePassword='',
                     market='cny',
                     withdrawFee=0.0001):
        """提币"""
        method = FUNCTIONCODE_WITHDRAWCOIN
        params = {
            'coin_type': coinType,
            'withdraw_address': withdrawAddress,
            'withdraw_amount': withdrawAmount
        }
        callback = self.onWithdrawCoin
        optional = {'market': market, 'withdraw_fee': withdrawFee}
        return self.sendRequest(method, params, callback, optional)

    def cancelWithdrawCoin(self, id_, market='cny'):
        """取消提币"""
        method = FUNCTIONCODE_CANCELWITHDRAWCOIN
        params = {'withdraw_coin_id': id_}
        callback = self.onCancelWithdrawCoin
        optional = {'market': market}
        return self.sendRequest(method, params, callback, optional)

    def onGetWithdrawCoinResult(self, id_, market='cny'):
        """查询提币结果"""
        method = FUNCTIONCODE_GETWITHDRAWCOINRESULT
        params = {'withdraw_coin_id': id_}
        callback = self.onGetWithdrawCoinResult
        optional = {'market': market}
        return self.sendRequest(method, params, callback, optional)

    def transfer(self, amountFrom, amountTo, amount, coinType=COINTYPE_BTC):
        """账户内转账"""
        method = FUNCTIONCODE_TRANSFER
        params = {
            'amount_from': amountFrom,
            'amount_to': amountTo,
            'amount': amount,
            'coin_type': coinType
        }
        callback = self.onTransfer
        optional = {}
        return self.sendRequest(method, params, callback, optional)

    def loan(self, amount, loan_type=LOANTYPE_CNY, market=MARKETTYPE_CNY):
        """申请杠杆"""
        method = FUNCTIONCODE_LOAN
        params = {'amount': amount, 'loan_type': loan_type}
        callback = self.onLoan
        optional = {'market': market}
        return self.sendRequest(method, params, callback, optional)

    def repayment(self, id_, amount, repayAll=0, market=MARKETTYPE_CNY):
        """归还杠杆"""
        method = FUNCTIONCODE_REPAYMENT
        params = {'loan_id': id_, 'amount': amount}
        callback = self.onRepayment
        optional = {'repay_all': repayAll, 'market': market}
        return self.sendRequest(method, params, callback, optional)

    def getLoanAvailable(self, market='cny'):
        """查询杠杆额度"""
        method = FUNCTIONCODE_GETLOANAVAILABLE
        params = {}
        callback = self.onLoanAvailable
        optional = {'market': market}
        return self.sendRequest(method, params, callback, optional)

    def getLoans(self, market='cny'):
        """查询杠杆列表"""
        method = FUNCTIONCODE_GETLOANS
        params = {}
        callback = self.onGetLoans
        optional = {'market': market}
        return self.sendRequest(method, params, callback, optional)

    def onError(self, error, req, reqID):
        """错误推送"""
        print(error, reqID)

    def onGetAccountInfo(self, data, req, reqID):
        """查询账户回调"""
        print(data)

    def onGetOrders(self, data, req, reqID, fuck):
        """查询委托回调"""
        print(data)

    def onOrderInfo(self, data, req, reqID):
        """委托详情回调"""
        print(data)

    def onBuy(self, data, req, reqID):
        """买入回调"""
        print(data)

    def onSell(self, data, req, reqID):
        """卖出回调"""
        print(data)

    def onBuyMarket(self, data, req, reqID):
        """市价买入回调"""
        print(data)

    def onSellMarket(self, data, req, reqID):
        """市价卖出回调"""
        print(data)

    def onCancelOrder(self, data, req, reqID):
        """撤单回调"""
        print(data)

    def onGetNewDealOrders(self, data, req, reqID):
        """查询最新成交回调"""
        print(data)

    def onGetOrderIdByTradeId(self, data, req, reqID):
        """通过成交编号查询委托编号回调"""
        print(data)

    def onWithdrawCoin(self, data, req, reqID):
        """提币回调"""
        print(data)

    def onCancelWithdrawCoin(self, data, req, reqID):
        """取消提币回调"""
        print(data)

    def onTransfer(self, data, req, reqID):
        """转账回调"""
        print(data)

    def onLoan(self, data, req, reqID):
        """申请杠杆回调"""
        print(data)

    def onRepayment(self, data, req, reqID):
        """归还杠杆回调"""
        print(data)

    def onLoanAvailable(self, data, req, reqID):
        """查询杠杆额度回调"""
        print(data)

    def onGetLoans(self, data, req, reqID):
        """查询杠杆列表"""
        print(data)


########################################################################
class DataApi(object):
    """行情接口"""
    DEBUG = True

    def __init__(self):
        """Constructor"""
        self.active = False
        self.taskInterval = 0  # 每轮请求延时
        self.taskList = []  # 订阅的任务列表
        self.client = Client('', '')
        self.taskThread = Thread(target=self.run)  # 处理任务的线程

    def init(self, accessKey, secretKey, interval, debug):
        """初始化"""
        self.taskInterval = interval
        self.DEBUG = debug
        self.client = Client(accessKey, secretKey)
        self.active = True
        self.taskThread.start()

    def exit(self):
        """退出"""
        self.active = False

        if self.taskThread.isAlive():
            self.taskThread.join()

    def run(self):
        """连续运行"""
        while self.active:
            for symbol, callback in self.taskList:
                try:
                    data = self.client.get_order_book(symbol)
                    if self.DEBUG:
                        print(callback.__name__)
                    callback(data)
                except:
                    traceback.print_exc()

            sleep(self.taskInterval)

    def subscribeTick(self, symbol):
        """订阅实时成交数据"""
        task = (symbol, self.onTick)
        self.taskList.append(task)

    def subscribeQuote(self, symbol):
        """订阅实时报价数据"""
        task = (symbol, self.onQuote)
        self.taskList.append(task)

    def subscribeDepth(self, symbol, level=0):
        """订阅深度数据"""
        task = (symbol, self.onDepth)
        self.taskList.append(task)

    def onTick(self, data):
        """实时成交推送"""
        print(data)

    def onQuote(self, data):
        """实时报价推送"""
        print(data)

    def onDepth(self, data):
        """实时深度推送"""
        print(data)