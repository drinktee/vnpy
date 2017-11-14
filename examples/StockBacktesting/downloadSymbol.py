__author__ = 'foursking'

from vnpy.trader.app.stockStrategy.stockBase import MINUTE_DB_NAME
from vnpy.trader.app.stockStrategy.stockHistoryData import HistoryDataEngine

if __name__ == '__main__':
    his = HistoryDataEngine()
    his.downloadFuturesSymbol()