# encoding: utf-8
__author__ = 'foursking'
import tushare as ts

import urllib
import hashlib

import json
import requests
from time import time, sleep
from Queue import Queue, Empty
from threading import Thread

class DataApi(object):

    DEBUG = True

    #----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        self.active = False

        self.taskInterval = 0                       # 每轮请求延时
        self.taskList = []                          # 订阅的任务列表
        self.taskThread = Thread(target=self.run)   # 处理任务的线程

    #----------------------------------------------------------------------
    def init(self, interval, debug):
        """初始化"""
        self.taskInterval = interval
        self.DEBUG = debug

        self.active = True
        self.taskThread.start()

    #----------------------------------------------------------------------
    def exit(self):
        """退出"""
        self.active = False

        if self.taskThread.isAlive():
            self.taskThread.join()

    #----------------------------------------------------------------------
    def run(self):
        """连续运行"""
        while self.active:
            for symbol, callback in self.taskList:
                try:
                    df = ts.get_realtime_quotes('000581')
                    if self.DEBUG:
                        print callback.__name__
                    callback(df)
                except Exception, e:
                    print e

            sleep(self.taskInterval)

    #----------------------------------------------------------------------
    def subscribeTick(self, symbol):
        """订阅实时成交数据"""
        task = (symbol, self.onTick)
        self.taskList.append(task)

    #----------------------------------------------------------------------
    def subscribeQuote(self, symbol):
        """订阅实时报价数据"""
        task = (symbol, self.onQuote)
        self.taskList.append(task)

    def subscribeDepth(self, symbol):
        """订阅深度数据"""
        task = (symbol, self.onDepth)
        self.taskList.append(task)

    #----------------------------------------------------------------------
    def onTick(self, data):
        """实时成交推送"""
        print data

    #----------------------------------------------------------------------
    def onQuote(self, data):
        """实时报价推送"""
        print data

    #----------------------------------------------------------------------
    def onDepth(self, data):
        """实时深度推送"""
        print data