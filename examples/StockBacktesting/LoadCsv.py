# encoding: UTF-8

"""
导入MC导出的CSV历史数据到MongoDB中
"""

from vnpy.trader.app.stockStrategy.stockBase import MINUTE_DB_NAME
from vnpy.trader.app.stockStrategy.stockHistoryData import loadWxCsv


if __name__ == '__main__':
    loadWxCsv('SH000001.csv', MINUTE_DB_NAME, 'SH000001')

