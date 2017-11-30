__author__ = 'foursking'
# encoding: UTF-8

from datetime import datetime, timedelta
from time import time
from multiprocessing.pool import ThreadPool

import pymongo

import tushare as ts
from vnpy.data.datayes import DatayesApi
from vnpy.trader.vtGlobal import globalSetting
from vnpy.trader.vtConstant import *
from vnpy.trader.vtObject import VtBarData
from .stockBase import SETTING_DB_NAME, TICK_DB_NAME, MINUTE_DB_NAME, DAILY_DB_NAME


# 以下为vn.trader和通联数据规定的交易所代码映射
VT_TO_DATAYES_EXCHANGE = {}
VT_TO_DATAYES_EXCHANGE[EXCHANGE_CFFEX] = 'CCFX'     # 中金所
VT_TO_DATAYES_EXCHANGE[EXCHANGE_SHFE] = 'XSGE'      # 上期所
VT_TO_DATAYES_EXCHANGE[EXCHANGE_CZCE] = 'XZCE'       # 郑商所
VT_TO_DATAYES_EXCHANGE[EXCHANGE_DCE] = 'XDCE'       # 大商所
DATAYES_TO_VT_EXCHANGE = {v:k for k,v in VT_TO_DATAYES_EXCHANGE.items()}


class HistoryDataEngine(object):
    """CTA模块用的历史数据引擎"""

    #----------------------------------------------------------------------
    def __init__(self):
        self.dbClient = pymongo.MongoClient(globalSetting['mongoHost'], globalSetting['mongoPort'])

    #---------------------------------------------------------------------
    def lastTradeDate(self):
        """获取最近交易日（只考虑工作日，无法检查国内假期）"""
        today = datetime.now()
        oneday = timedelta(1)

        if today.weekday() == 5:
            today = today - oneday
        elif today.weekday() == 6:
            today = today - oneday*2

        return today.strftime('%Y%m%d')

    def readStockProductSymbol(self):
        """查询所有期货产品代码"""
        cx = self.dbClient[SETTING_DB_NAME]['FuturesSymbol'].find()
        return set([d['productSymbol'] for d in cx])    # 这里返回的是集合（因为会重复）

    #----------------------------------------------------------------------
    def downloadFuturesSymbol(self, tradeDate=''):
        """下载所有期货的代码"""
        if not tradeDate:
            tradeDate = self.lastTradeDate()

        self.dbClient[SETTING_DB_NAME]['StockSymbol'].ensure_index([('symbol', pymongo.ASCENDING)],
                                                                       unique=True)
        data = ts.get_concept_classified()

        for idx, d in data.iterrows():
            symbolDict = {}
            symbolDict['symbol'] = d['code']
            symbolDict['name'] = d['name']
            symbolDict['c_name'] = d['c_name']
            flt = {'symbol': d['code']}
            self.dbClient[SETTING_DB_NAME]['StockSymbol'].update_one(flt, {'$set':symbolDict},                                                                           upsert=True)
            print u'期货合约代码下载完成'


#----------------------------------------------------------------------
def downloadEquityDailyBarts(self, symbol):
    """
    下载股票的日行情，symbol是股票代码
    """
    print u'开始下载%s日行情' %symbol

    # 查询数据库中已有数据的最后日期
    cl = self.dbClient[DAILY_DB_NAME][symbol]
    cx = cl.find(sort=[('datetime', pymongo.DESCENDING)])
    if cx.count():
        last = cx[0]
    else:
        last = ''
    # 开始下载数据
    import tushare as ts

    if last:
        start = last['date'][:4]+'-'+last['date'][4:6]+'-'+last['date'][6:]

    data = ts.get_k_data(symbol,start)

    if not data.empty:
        # 创建datetime索引
        self.dbClient[DAILY_DB_NAME][symbol].ensure_index([('datetime', pymongo.ASCENDING)],
                                                            unique=True)

        for index, d in data.iterrows():
            bar = VtBarData()
            bar.vtSymbol = symbol
            bar.symbol = symbol
            try:
                bar.open = d.get('open')
                bar.high = d.get('high')
                bar.low = d.get('low')
                bar.close = d.get('close')
                bar.date = d.get('date').replace('-', '')
                bar.time = ''
                bar.datetime = datetime.strptime(bar.date, '%Y%m%d')
                bar.volume = d.get('volume')
            except KeyError:
                print d

            flt = {'datetime': bar.datetime}
            self.dbClient[DAILY_DB_NAME][symbol].update_one(flt, {'$set':bar.__dict__}, upsert=True)

        print u'%s下载完成' %symbol
    else:
        print u'找不到合约%s' %symbol

def loadWxCsv(fileName, dbName, symbol):
    import csv

    start = time()
    print u'开始读取CSV文件%s中的数据插入到%s的%s中' %(fileName, dbName, symbol)

        # 锁定集合，并创建索引
    client = pymongo.MongoClient(globalSetting['mongoHost'], globalSetting['mongoPort'])
    collection = client[dbName][symbol]
    collection.ensure_index([('datetime', pymongo.ASCENDING)], unique=True)

    # 读取数据和插入到数据库
    reader = csv.DictReader(file(fileName, 'r'))
    for d in reader:
        bar = VtBarData()
        bar.vtSymbol = symbol
        bar.symbol = symbol
        bar.open = float(d['Open'])
        bar.high = float(d['High'])
        bar.low = float(d['Low'])
        bar.close = float(d['Close'])

        date_obj = datetime.strptime(d['Date'], '%Y-%m-%d %H:%M:%S')
        bar.date = date_obj.strftime('%Y%m%d')
        bar.time = date_obj.strftime('%H:%M:%S')
        bar.datetime = datetime.strptime(bar.date + ' ' + bar.time, '%Y%m%d %H:%M:%S')
        bar.volume = d['Volume']

        flt = {'datetime': bar.datetime}
        collection.update_one(flt, {'$set':bar.__dict__}, upsert=True)
        print bar.date, bar.time

    print u'插入完毕，耗时：%s' % (time()-start)


#----------------------------------------------------------------------
def loadMcCsv(fileName, dbName, symbol):
    """将Multicharts导出的csv格式的历史数据插入到Mongo数据库中"""
    import csv

    start = time()
    print u'开始读取CSV文件%s中的数据插入到%s的%s中' %(fileName, dbName, symbol)

    # 锁定集合，并创建索引
    client = pymongo.MongoClient(globalSetting['mongoHost'], globalSetting['mongoPort'])
    collection = client[dbName][symbol]
    collection.ensure_index([('datetime', pymongo.ASCENDING)], unique=True)

    # 读取数据和插入到数据库
    reader = csv.DictReader(file(fileName, 'r'))
    for d in reader:
        bar = VtBarData()
        bar.vtSymbol = symbol
        bar.symbol = symbol
        bar.open = float(d['Open'])
        bar.high = float(d['High'])
        bar.low = float(d['Low'])
        bar.close = float(d['Close'])
        bar.date = datetime.strptime(d['Date'], '%Y-%m-%d').strftime('%Y%m%d')
        bar.time = d['Time']
        bar.datetime = datetime.strptime(bar.date + ' ' + bar.time, '%Y%m%d %H:%M:%S')
        bar.volume = d['TotalVolume']

        flt = {'datetime': bar.datetime}
        collection.update_one(flt, {'$set':bar.__dict__}, upsert=True)
        print bar.date, bar.time

    print u'插入完毕，耗时：%s' % (time()-start)

#----------------------------------------------------------------------
def loadTbCsv(fileName, dbName, symbol):
    """将TradeBlazer导出的csv格式的历史分钟数据插入到Mongo数据库中"""
    import csv

    start = time()
    print u'开始读取CSV文件%s中的数据插入到%s的%s中' %(fileName, dbName, symbol)

    # 锁定集合，并创建索引
    client = pymongo.MongoClient(globalSetting['mongoHost'], globalSetting['mongoPort'])
    collection = client[dbName][symbol]
    collection.ensure_index([('datetime', pymongo.ASCENDING)], unique=True)

    # 读取数据和插入到数据库
    reader = csv.reader(file(fileName, 'r'))
    for d in reader:
        bar = VtBarData()
        bar.vtSymbol = symbol
        bar.symbol = symbol
        bar.open = float(d[1])
        bar.high = float(d[2])
        bar.low = float(d[3])
        bar.close = float(d[4])
        bar.date = datetime.strptime(d[0].split(' ')[0], '%Y/%m/%d').strftime('%Y%m%d')
        bar.time = d[0].split(' ')[1]+":00"
        bar.datetime = datetime.strptime(bar.date + ' ' + bar.time, '%Y%m%d %H:%M:%S')
        bar.volume = d[5]
        bar.openInterest = d[6]

        flt = {'datetime': bar.datetime}
        collection.update_one(flt, {'$set':bar.__dict__}, upsert=True)
        print bar.date, bar.time

    print u'插入完毕，耗时：%s' % (time()-start)

 #----------------------------------------------------------------------
def loadTbPlusCsv(fileName, dbName, symbol):
    """将TB极速版导出的csv格式的历史分钟数据插入到Mongo数据库中"""
    import csv

    start = time()
    print u'开始读取CSV文件%s中的数据插入到%s的%s中' %(fileName, dbName, symbol)

    # 锁定集合，并创建索引
    client = pymongo.MongoClient(globalSetting['mongoHost'], globalSetting['mongoPort'])
    collection = client[dbName][symbol]
    collection.ensure_index([('datetime', pymongo.ASCENDING)], unique=True)

    # 读取数据和插入到数据库
    reader = csv.reader(file(fileName, 'r'))
    for d in reader:
        bar = VtBarData()
        bar.vtSymbol = symbol
        bar.symbol = symbol
        bar.open = float(d[2])
        bar.high = float(d[3])
        bar.low = float(d[4])
        bar.close = float(d[5])
        bar.date = str(d[0])

        tempstr=str(round(float(d[1])*10000)).split(".")[0].zfill(4)
        bar.time = tempstr[:2]+":"+tempstr[2:4]+":00"

        bar.datetime = datetime.strptime(bar.date + ' ' + bar.time, '%Y%m%d %H:%M:%S')
        bar.volume = d[6]
        bar.openInterest = d[7]
        flt = {'datetime': bar.datetime}
        collection.update_one(flt, {'$set':bar.__dict__}, upsert=True)
        print bar.date, bar.time

    print u'插入完毕，耗时：%s' % (time()-start)


#----------------------------------------------------------------------
def loadTdxCsv(fileName, dbName, symbol):
    """将通达信导出的csv格式的历史分钟数据插入到Mongo数据库中"""
    import csv

    start = time()
    print u'开始读取CSV文件%s中的数据插入到%s的%s中' %(fileName, dbName, symbol)

    # 锁定集合，并创建索引
    client = pymongo.MongoClient(globalSetting['mongoHost'], globalSetting['mongoPort'])
    collection = client[dbName][symbol]
    collection.ensure_index([('datetime', pymongo.ASCENDING)], unique=True)

    # 读取数据和插入到数据库
    reader = csv.reader(file(fileName, 'r'))
    for d in reader:
        bar = VtBarData()
        bar.vtSymbol = symbol
        bar.symbol = symbol
        bar.open = float(d[2])
        bar.high = float(d[3])
        bar.low = float(d[4])
        bar.close = float(d[5])
        bar.date = datetime.strptime(d[0], '%Y/%m/%d').strftime('%Y%m%d')
        bar.time = d[1][:2]+':'+d[1][2:4]+':00'
        bar.datetime = datetime.strptime(bar.date + ' ' + bar.time, '%Y%m%d %H:%M:%S')
        bar.volume = d[6]
        bar.openInterest = d[7]

        flt = {'datetime': bar.datetime}
        collection.update_one(flt, {'$set':bar.__dict__}, upsert=True)
        print bar.date, bar.time

    print u'插入完毕，耗时：%s' % (time()-start)


