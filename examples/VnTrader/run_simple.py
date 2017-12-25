# encoding: UTF-8

# 重载sys模块，设置默认字符串编码方式为utf8
import sys

reload(sys)
sys.setdefaultencoding('utf8')

# 判断操作系统
import platform

system = platform.system()

# vn.trader模块
from vnpy.event import EventEngine
from vnpy.trader.vtEngine import MainEngine
from vnpy.trader.uiQt import createQApp
from vnpy.trader.uiMainWindow import MainWindow

# 加载底层接口
from vnpy.trader.gateway import ctpGateway
from vnpy.trader.gateway import okexGateway
from  vnpy.trader.gateway.okexGateway.okexGateway import BTC_USD_SPOT
# 加载上层应用
from vnpy.trader.app import (riskManager, ctaStrategy, spreadTrading)


# ----------------------------------------------------------------------
def main():
    """主程序入口"""
    # 创建Qt应用对象
    qApp = createQApp()

    # 创建事件引擎
    ee = EventEngine()

    # 创建主引擎
    me = MainEngine(ee)

    # 添加交易接口
    # me.addGateway(ctpGateway)
    me.addGateway(okexGateway)
    #me.subscribe(BTC_USD_SPOT, "OKEX")

    # 添加上层应用
    me.addApp(riskManager)
    me.addApp(ctaStrategy)
    me.addApp(spreadTrading)

    # 创建主窗口
    mw = MainWindow(me, ee)
    mw.showMaximized()

    # 在主线程中启动Qt事件循环
    sys.exit(qApp.exec_())


if __name__ == '__main__':
    main()
