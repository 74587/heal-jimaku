#!/usr/bin/env python3
"""
治幕 (Heal-Jimaku) - 字幕处理工具主程序
负责应用初始化、高DPI设置和主窗口启动
"""

import sys
import os

# 确保能找到项目模块
if os.path.dirname(__file__) not in sys.path:
    sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, qInstallMessageHandler, QtMsgType

def qt_message_handler(mode, _context, message):
    """自定义 Qt 消息处理器，过滤掉 QPainter 警告"""
    # 过滤掉 QPainter 相关的非致命警告
    if "QPainter" in message and (
        "Paint device returned engine == 0" in message or
        "Painter not active" in message
    ):
        return  # 静默忽略这些警告

    # 其他消息正常输出
    if mode == QtMsgType.QtDebugMsg:
        print(f"Qt Debug: {message}")
    elif mode == QtMsgType.QtWarningMsg:
        print(f"Qt Warning: {message}")
    elif mode == QtMsgType.QtCriticalMsg:
        print(f"Qt Critical: {message}")
    elif mode == QtMsgType.QtFatalMsg:
        print(f"Qt Fatal: {message}")
        sys.exit(1)

from utils.file_utils import resource_path, setup_faulthandler
from ui.main_window import HealJimakuApp

if __name__ == "__main__":
    try:
        # 安装自定义消息处理器，过滤 QPainter 警告
        qInstallMessageHandler(qt_message_handler)

        setup_faulthandler()

        # 检查并执行数据迁移
        try:
            from utils.migration import check_legacy_data, migrate_legacy_data
            if check_legacy_data():
                print("检测到旧版本数据，正在迁移...")
                success, message = migrate_legacy_data()
                if success:
                    print(f"数据迁移完成: {message}")
                else:
                    print(f"数据迁移失败: {message}")
        except Exception as e:
            print(f"数据迁移检查失败: {e}")

        app = QApplication(sys.argv)
    except Exception as e:
        print(f"[Error] 应用初始化失败: {e}")
        sys.exit(1)

    high_dpi_scaling_set = False
    high_dpi_pixmaps_set = False

    # 设置高DPI支持
    try:
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
            high_dpi_scaling_set = True

        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
            high_dpi_pixmaps_set = True

    except AttributeError as e:
        print(f"警告: 设置高DPI属性时遇到 AttributeError: {e}")
    except Exception as e_generic:
        print(f"警告: 设置高DPI属性时发生未知错误: {e_generic}")

    app.setApplicationName("HealJimaku")

    # Windows系统设置应用ID
    if os.name == 'nt':
        try:
            import ctypes
            myappid_str = 'fuxiaomoke.HealJimaku.Refactored.Project.0.0.3'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid_str)
        except Exception:
            pass

    # 设置应用图标
    app_icon_early_path = resource_path("icon.ico")
    if app_icon_early_path and os.path.exists(app_icon_early_path):
        app.setWindowIcon(QIcon(app_icon_early_path))
    else:
        print("[Log Early Main] 应用图标 'icon.ico' 在主程序启动时未找到。")

    # 启动主窗口
    try:
        window = HealJimakuApp()
        window.show()
        result = app.exec()
        sys.exit(result)
    except Exception as e:
        print(f"[Error] 应用运行时错误: {e}")
        sys.exit(1)