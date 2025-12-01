import sys
import os
import faulthandler

def resource_path(relative_path):
    """获取资源的绝对路径，兼容开发环境和打包后的运行环境

    Args:
        relative_path (str): 相对于assets目录的文件路径

    Returns:
        str or None: 资源的绝对路径，找不到则返回None
    """
    path = None
    try:
        # PyInstaller打包后的环境：资源存储在_MEIPASS临时文件夹中
        base_path = sys._MEIPASS  # type: ignore
        path = os.path.join(base_path, "assets", relative_path)
        if not os.path.exists(path):
            # 尝试不带assets子目录的路径
            path = os.path.join(base_path, relative_path)
    except AttributeError:
        # 开发环境：根据文件路径计算项目根目录
        current_file_dir = os.path.abspath(os.path.dirname(__file__))
        src_dir = os.path.dirname(current_file_dir)
        project_root = os.path.dirname(src_dir)

        # 优先尝试项目根目录下的assets文件夹
        path_in_project_assets = os.path.join(project_root, "assets", relative_path)
        if os.path.exists(path_in_project_assets):
            path = path_in_project_assets
        else:
            path = None

    # 验证路径是否存在
    if path and not os.path.exists(path):
        return None
    return path


def setup_faulthandler():
    """初始化错误处理模块，用于捕获和记录程序崩溃信息

    根据运行环境选择合适的日志输出方式：
    - GUI应用（无stderr）：将日志写入用户目录下的文件
    - 命令行应用（有stderr）：输出到stderr
    """
    try:
        if sys.stderr is None:
            # GUI应用环境，将日志写入文件
            log_dir_app = ""
            try:
                # 导入新的目录定义
                import config
                log_dir_app = config.LOGS_DIR
                if not os.path.exists(log_dir_app):
                    os.makedirs(log_dir_app, exist_ok=True)

                # 确保基础目录结构存在
                if not os.path.exists(config.BASE_DIR):
                    os.makedirs(config.BASE_DIR, exist_ok=True)
                if not os.path.exists(config.CONFIG_DIR):
                    os.makedirs(config.CONFIG_DIR, exist_ok=True)
                crash_log_path = config.CRASH_LOG_FILE
                with open(crash_log_path, 'a', encoding='utf-8') as f_log:
                    faulthandler.enable(file=f_log, all_threads=True)
                print(f"Faulthandler enabled, logging to: {crash_log_path}")
            except Exception as e_fh_file:
                print(f"Failed to enable faulthandler to file: {e_fh_file}")
                pass
        else:
            # 命令行环境，输出到stderr
            faulthandler.enable(all_threads=True)
    except Exception as e_fh_setup:
        print(f"Failed to setup faulthandler: {e_fh_setup}")
        pass