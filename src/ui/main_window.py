import os
import json
import logging
import traceback
from typing import Optional, Any, Dict, List
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox,
    QProgressBar, QGroupBox, QTextEdit, QCheckBox, QComboBox,
    QAbstractItemView, QDialog, QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QThread, QSize, pyqtSignal, QRect
from PyQt6.QtGui import QIcon, QFont, QColor, QTextCursor, QPixmap, QPainter, QBrush, QLinearGradient, QPainterPath, QFontDatabase

import config as app_config

from config import (
    CONFIG_DIR, CONFIG_FILE,
    USER_MIN_DURATION_TARGET_KEY, USER_MAX_DURATION_KEY,
    USER_MAX_CHARS_PER_LINE_KEY, USER_DEFAULT_GAP_MS_KEY,
    DEFAULT_MIN_DURATION_TARGET, DEFAULT_MAX_DURATION,
    DEFAULT_MAX_CHARS_PER_LINE, DEFAULT_DEFAULT_GAP_MS,
    USER_FREE_TRANSCRIPTION_LANGUAGE_KEY,
    USER_FREE_TRANSCRIPTION_NUM_SPEAKERS_KEY,
    USER_FREE_TRANSCRIPTION_TAG_AUDIO_EVENTS_KEY,
    DEFAULT_FREE_TRANSCRIPTION_LANGUAGE,
    DEFAULT_FREE_TRANSCRIPTION_NUM_SPEAKERS,
    DEFAULT_FREE_TRANSCRIPTION_TAG_AUDIO_EVENTS,
    USER_LLM_API_BASE_URL_KEY, USER_LLM_MODEL_NAME_KEY,
    USER_LLM_API_KEY_KEY, USER_LLM_REMEMBER_API_KEY_KEY, USER_LLM_TEMPERATURE_KEY,
    DEFAULT_LLM_API_BASE_URL, DEFAULT_LLM_MODEL_NAME,
    DEFAULT_LLM_API_KEY, DEFAULT_LLM_REMEMBER_API_KEY, DEFAULT_LLM_TEMPERATURE,
    LLM_PROFILES_KEY, CURRENT_PROFILE_ID_KEY, DEFAULT_CURRENT_PROFILE_ID,
    USER_CUSTOM_BACKGROUND_FOLDER_KEY, USER_ENABLE_RANDOM_BACKGROUND_KEY,
    USER_FIXED_BACKGROUND_PATH_KEY, USER_BACKGROUND_SOURCE_KEY,
    USER_REMEMBERED_CUSTOM_FOLDER_KEY, USER_REMEMBERED_CUSTOM_IMAGE_KEY,
    DEFAULT_CUSTOM_BACKGROUND_FOLDER, DEFAULT_ENABLE_RANDOM_BACKGROUND,
    DEFAULT_FIXED_BACKGROUND_PATH, DEFAULT_BACKGROUND_SOURCE,
    DEFAULT_REMEMBERED_CUSTOM_FOLDER, DEFAULT_REMEMBERED_CUSTOM_IMAGE,
    BACKGROUND_SOURCE_USER_SELECTED, BACKGROUND_SOURCE_CAROUSEL_FIXED,
    # 云端转录配置
    USER_CLOUD_TRANSCRIPTION_PROVIDER_KEY,
    USER_ELEVENLABS_API_KEY_KEY, USER_ELEVENLABS_API_REMEMBER_KEY_KEY,
    USER_ELEVENLABS_API_LANGUAGE_KEY, USER_ELEVENLABS_API_NUM_SPEAKERS_KEY,
    USER_ELEVENLABS_API_ENABLE_DIARIZATION_KEY, USER_ELEVENLABS_API_TAG_AUDIO_EVENTS_KEY,
    USER_SONIOX_API_KEY_KEY, USER_SONIOX_API_REMEMBER_KEY_KEY,
    USER_SONIOX_LANGUAGE_HINTS_KEY, USER_SONIOX_ENABLE_SPEAKER_DIARIZATION_KEY,
    USER_SONIOX_ENABLE_LANGUAGE_IDENTIFICATION_KEY, USER_SONIOX_CONTEXT_TERMS_KEY,
    USER_SONIOX_CONTEXT_TEXT_KEY, USER_SONIOX_CONTEXT_GENERAL_KEY,
    DEFAULT_CLOUD_TRANSCRIPTION_PROVIDER,
    DEFAULT_ELEVENLABS_API_KEY, DEFAULT_ELEVENLABS_API_REMEMBER_KEY,
    DEFAULT_ELEVENLABS_API_LANGUAGE, DEFAULT_ELEVENLABS_API_NUM_SPEAKERS,
    DEFAULT_ELEVENLABS_API_ENABLE_DIARIZATION, DEFAULT_ELEVENLABS_API_TAG_AUDIO_EVENTS,
    DEFAULT_SONIOX_API_KEY, DEFAULT_SONIOX_API_REMEMBER_KEY,
    DEFAULT_SONIOX_LANGUAGE_HINTS, DEFAULT_SONIOX_ENABLE_SPEAKER_DIARIZATION,
    DEFAULT_SONIOX_ENABLE_LANGUAGE_IDENTIFICATION, DEFAULT_SONIOX_CONTEXT_TERMS,
    DEFAULT_SONIOX_CONTEXT_TEXT, DEFAULT_SONIOX_CONTEXT_GENERAL
)

from utils.file_utils import resource_path
from utils.user_friendly_logger import user_logger, MessageLevel
from .custom_widgets import TransparentWidget, CustomLabel, CustomLabel_title, StrokeCheckBoxWidget
from .conversion_worker import ConversionWorker
from .controllers.conversion_controller import ConversionController
from core.srt_processor import SrtProcessor
from .settings_dialog import SettingsDialog
from .cloud_transcription_dialog import CloudTranscriptionDialog
from .free_transcription_dialog import FreeTranscriptionDialog
from core.elevenlabs_api import ElevenLabsSTTClient
from .llm_advanced_settings_dialog import LlmAdvancedSettingsDialog, LlmTestWorker
from .background_manager import BackgroundManager
from .background_settings_dialog import BackgroundSettingsDialog


class HealJimakuApp(QMainWindow):
    """
    治幕应用主窗口类

    负责管理整个应用的UI界面、用户交互、文件处理流程和配置管理。
    包含音频转录、字幕生成、批量处理等核心功能。
    """
    _log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Heal-Jimaku (治幕)")

        # 初始化核心组件
        self.srt_processor = SrtProcessor()
        self.elevenlabs_stt_client = ElevenLabsSTTClient()
        self.config: Dict[str, Any] = {}

        # 初始化转换控制器 - 负责所有转换任务的业务逻辑
        self.conversion_controller = ConversionController(
            config_manager=self,  # 传递main_window实例，它有config属性
            elevenlabs_client=self.elevenlabs_stt_client,
            srt_processor=self.srt_processor
        )

        # 连接控制器信号到UI更新方法
        self.conversion_controller.task_started.connect(self._on_task_started)
        self.conversion_controller.task_finished.connect(self._on_task_finished)
        self.conversion_controller.progress_updated.connect(self.update_progress)
        self.conversion_controller.upload_progress.connect(self._on_upload_progress)
        self.conversion_controller.log_message.connect(self.log_message)

        self.app_icon: Optional[QIcon] = None
        self.background: Optional[QPixmap] = None  # 当前显示的背景（已缩放）
        self.original_background: Optional[QPixmap] = None  # 原始背景图片（未缩放）

        # 初始化背景管理器
        self.background_manager = BackgroundManager()
        self.background_settings = {
            'enable_random': DEFAULT_ENABLE_RANDOM_BACKGROUND,
            'custom_folder': DEFAULT_CUSTOM_BACKGROUND_FOLDER,
            'fixed_background_path': DEFAULT_FIXED_BACKGROUND_PATH,
            'background_source': DEFAULT_BACKGROUND_SOURCE
        }
        self.settings_button: Optional[QPushButton] = None
        self.free_transcription_button: Optional[QPushButton] = None
        self.llm_advanced_settings_button: Optional[QPushButton] = None
        self.background_settings_button: Optional[QPushButton] = None

        self.is_dragging = False
        self.drag_pos = QPoint()

        # 窗口大小调整相关变量
        self._resize_border_width = 8  # 边框宽度
        self._resize_mode = 0  # 调整大小模式 (0:无, 1:左, 2:右, 4:上, 8:下, 组合值表示角)
        self._resize_start_pos = QPoint()
        self._resize_start_geometry = None

        # 设置窗口为无标题栏但有边框模式
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # 添加大小调整支持
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)  # 启用鼠标追踪，用于检测边框拖拽

        self.log_area_early_messages: list[str] = []
        self.advanced_srt_settings: Dict[str, Any] = {}
        self.free_transcription_settings: Dict[str, Any] = {}
        self.cloud_transcription_settings: Dict[str, Any] = {}
        self.llm_advanced_settings: Dict[str, Any] = {}
        self._current_input_mode = "local_json"
        self._temp_audio_file_for_free_transcription: Optional[str] = None
        self._batch_files: List[str] = []  # 批量JSON文件列表
        self._batch_audio_files: List[str] = []  # 批量音频文件列表

        # 跟踪免费转录按钮的状态
        self._free_transcription_button_is_in_cancel_mode = False

        icon_path_str = resource_path("icon.ico")
        if icon_path_str and os.path.exists(icon_path_str):
            self.app_icon = QIcon(icon_path_str)
        else:
            self._early_log("警告: 应用图标 icon.ico 未找到。")
            self.app_icon = QIcon()
        self.setWindowIcon(self.app_icon)

        # 恢复简单的中央部件设置
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.main_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)


        # 拖拽处理相关变量
        self.drag_overlay_widget: Optional[QWidget] = None
        self.is_drag_overlay_visible = False

        # 启用拖拽接收
        self.setAcceptDrops(True)
        self.main_widget.setAcceptDrops(True)

        self.api_key_entry: Optional[QLineEdit] = None
        self.api_key_visibility_button: Optional[QPushButton] = None
        self.test_connection_button: Optional[QPushButton] = None
        self.test_connection_thread: Optional[QThread] = None
        self.test_connection_worker: Optional[LlmTestWorker] = None
        self.json_path_entry: Optional[QLineEdit] = None
        self.json_browse_button: Optional[QPushButton] = None
        self.json_format_combo: Optional[QComboBox] = None
        self.ai_correction_check: Optional[StrokeCheckBoxWidget] = None
        self.output_path_entry: Optional[QLineEdit] = None
        self.output_browse_button: Optional[QPushButton] = None
        self.progress_bar: Optional[QProgressBar] = None
        self.start_button: Optional[QPushButton] = None
        self.log_area: Optional[QTextEdit] = None

        self.init_ui()
        self._log_signal.connect(self.log_message)
        self._process_early_logs()

        # --- 正确的加载顺序 ---
        # 1. 先加载配置
        self.load_config()

        # 2. 先加载背景（这样background_manager.last_background_path就有实际值了）
        self._load_background()

        # 3. 再根据实际加载的背景调整窗口大小
        self._init_adaptive_window_size()

        self.center_window()
        QTimer.singleShot(100, self.apply_taskbar_icon)

        # 自动刷新所有配置的模型列表（静默操作）
        QTimer.singleShot(200, self._auto_refresh_all_models_on_startup)

    def _early_log(self, message: str):
        if hasattr(self, 'log_area') and self.log_area and self.log_area.isVisible():
            self.log_message(message)
        else:
            self.log_area_early_messages.append(message)
            print(f"[早期日志]: {message}")

    def _process_early_logs(self):
        if hasattr(self, 'log_area') and self.log_area:
            for msg in self.log_area_early_messages:
                self.log_message(msg)
            self.log_area_early_messages = []

    def _load_background(self):
        """加载背景图片（随机选择）"""
        # 初始化时使用默认设置（随机背景开启）
        enable_random = DEFAULT_ENABLE_RANDOM_BACKGROUND
        custom_folder = DEFAULT_CUSTOM_BACKGROUND_FOLDER

        try:
            # 尝试获取已初始化的设置，如果还没有则使用默认值
            if hasattr(self, 'background_settings'):
                enable_random = self.background_settings.get('enable_random', DEFAULT_ENABLE_RANDOM_BACKGROUND)
                custom_folder = self.background_settings.get('custom_folder', DEFAULT_CUSTOM_BACKGROUND_FOLDER)

                # 设置自定义背景文件夹
                if custom_folder and os.path.exists(custom_folder):
                    self.background_manager.set_custom_background_folder(custom_folder)
        except Exception as e:
            self._early_log(f"读取背景配置时出错: {e}")
            enable_random = DEFAULT_ENABLE_RANDOM_BACKGROUND

        # 加载背景图片
        if enable_random:
            # 随机选择背景
            self.original_background = self.background_manager.load_random_background_pixmap()
            if self.original_background:
                bg_info = self.background_manager.get_background_info()
                bg_filename = os.path.basename(self.background_manager.last_background_path) if self.background_manager.last_background_path else "未知"
                self._early_log(f"已加载随机背景图片: {bg_filename}，共 {bg_info['total_backgrounds']} 张可用背景")
        else:
            # 加载固定背景
            fixed_path = self.background_settings.get('fixed_background_path', '')
            if fixed_path:
                # 检查文件是否存在
                if os.path.exists(fixed_path):
                    # 使用指定的固定背景图片
                    self.original_background = self.background_manager.load_specific_background_pixmap(fixed_path)
                    if self.original_background:
                        bg_filename = os.path.basename(fixed_path)
                        self._early_log(f"已加载固定背景图片: {bg_filename}")
                    else:
                        self._early_log(f"固定背景图片损坏或格式不支持: {fixed_path}，使用默认背景")
                        # 回退到默认background.png并重置配置
                        self._load_default_background()
                        self._reset_background_settings_to_default()
                else:
                    self._early_log(f"固定背景图片不存在: {fixed_path}，使用默认背景")
                    # 回退到默认background.png并重置配置
                    self._load_default_background()
                    self._reset_background_settings_to_default()
            else:
                # 使用默认background.png
                self._load_default_background()

        # 如果背景加载失败，创建后备背景
        if self.original_background is None or self.original_background.isNull():
            self.original_background = self._create_fallback_background_pixmap()
            self._early_log("使用生成的渐变背景")
        else:
            # 自适应背景图片缩放，保持比例
            self._scale_background_to_window()

    def _create_fallback_background(self):
        """创建后备背景图片"""
        self.background = QPixmap(self.size())
        if self.background.isNull():
            # 如果创建失败，使用默认尺寸
            self.background = QPixmap(1024, 864)
        self.background.fill(Qt.GlobalColor.transparent)
        painter = QPainter(self.background)
        gradient = QLinearGradient(0, 0, 0, self.background.height())
        gradient.setColorAt(0, QColor(40, 40, 80, 200))
        gradient.setColorAt(1, QColor(20, 20, 40, 220))
        painter.fillRect(self.background.rect(), gradient)
        painter.end()

    def _create_fallback_background_pixmap(self):
        """创建后备背景图片并返回"""
        pixmap = QPixmap(1024, 864)
        if pixmap.isNull():
            # 如果创建失败，使用更小尺寸
            pixmap = QPixmap(512, 432)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        gradient = QLinearGradient(0, 0, 0, pixmap.height())
        gradient.setColorAt(0, QColor(40, 40, 80, 200))
        gradient.setColorAt(1, QColor(20, 20, 40, 220))
        painter.fillRect(pixmap.rect(), gradient)
        painter.end()
        return pixmap

    def _load_default_background(self):
        """加载默认的background.png"""
        bg_path_str = resource_path("background.png")
        if bg_path_str and os.path.exists(bg_path_str):
            self.original_background = QPixmap(bg_path_str)
            self._early_log("已加载默认背景图片 background.png")
        else:
            self._early_log("警告: 默认背景图片 background.png 未找到。")

    def _reset_background_settings_to_default(self):
        """重置背景设置为默认值（当固定背景图片丢失时）"""
        try:
            # 重置背景设置为默认值
            self.background_settings = {
                'enable_random': DEFAULT_ENABLE_RANDOM_BACKGROUND,
                'custom_folder': DEFAULT_CUSTOM_BACKGROUND_FOLDER,
                'fixed_background_path': DEFAULT_FIXED_BACKGROUND_PATH
            }

            # 更新配置
            self.config[USER_ENABLE_RANDOM_BACKGROUND_KEY] = DEFAULT_ENABLE_RANDOM_BACKGROUND
            self.config[USER_CUSTOM_BACKGROUND_FOLDER_KEY] = DEFAULT_CUSTOM_BACKGROUND_FOLDER
            self.config[USER_FIXED_BACKGROUND_PATH_KEY] = DEFAULT_FIXED_BACKGROUND_PATH

            # 保存配置到文件
            self._save_config()

            self._early_log("已自动重置背景设置为默认值（因为固定背景图片丢失）")
        except Exception as e:
            self._early_log(f"重置背景设置时出错: {e}")

    def refresh_background(self):
        """刷新背景图片（用于用户更改背景设置后）"""
        # 更新背景管理器设置
        if self.background_settings['custom_folder']:
            # 有自定义文件夹 - 设置自定义文件夹
            if not self.background_manager.set_custom_background_folder(self.background_settings['custom_folder']):
                self.log_message("警告: 无法设置自定义背景文件夹，路径不存在")
                self.background_manager.clear_custom_background_folder()
        else:
            # 没有自定义文件夹 - 清除自定义文件夹设置，恢复默认文件夹
            self.background_manager.clear_custom_background_folder()

        # 重新加载背景
        self._load_background()

        # 重新调整窗口大小以适应新的背景图片
        self._init_adaptive_window_size()

        # 重新居中窗口
        self.center_window()

        # 刷新界面显示
        self.update()

        # 保存配置
        self.save_config()

        # 记录日志
        if self.background_settings['enable_random']:
            bg_info = self.background_manager.get_background_info()
            custom_info = "（自定义文件夹）" if bg_info['custom_folder_enabled'] else ""
            self.log_message(f"背景已刷新：随机模式启用，共 {bg_info['total_backgrounds']} 张可用背景 {custom_info}")
        else:
            # 修复：记录实际的固定路径
            fixed_path = self.background_settings.get('fixed_background_path', 'DEFAULT')
            if fixed_path == 'DEFAULT' or not fixed_path:
                # 回退到默认 background.png 的情况
                default_bg_path = resource_path("background.png")
                if default_bg_path and os.path.exists(default_bg_path):
                    self.log_message("背景已刷新：固定模式 (background.png)")
                else:
                    self.log_message("背景已刷新：固定模式 (未找到特定图片，使用后备背景)")
            else:
                self.log_message(f"背景已刷新：固定模式 ({os.path.basename(fixed_path)})")

    def _log_early(self, message: str):
        """早期日志记录（在UI完全初始化之前）"""
        print(f"[早期日志]: {message}")
        if hasattr(self, 'log_area_early_messages'):
            self.log_area_early_messages.append(message)


    def apply_taskbar_icon(self):
        if hasattr(self, 'windowHandle') and self.windowHandle() is not None:
            if self.app_icon and not self.app_icon.isNull():
                self.windowHandle().setIcon(self.app_icon)
        elif self.app_icon and not self.app_icon.isNull():
            self.setWindowIcon(self.app_icon)

    def center_window(self):
        """将窗口居中显示在屏幕上"""
        try:
            screen = QApplication.primaryScreen()
            if screen:
                screen_geometry = screen.geometry()
                available_geometry = screen.availableGeometry()  # 考虑任务栏

                # 计算居中位置，使用可用几何区域
                x = (available_geometry.width() - self.width()) // 2 + available_geometry.x()
                y = (available_geometry.height() - self.height()) // 2 + available_geometry.y()

                self.move(x, y)
                self._log_early(f"窗口已居中: 位置({x}, {y})")
            else:
                # 如果无法获取屏幕信息，使用默认位置
                self.move(100, 100)
        except Exception as e:
            self._early_log(f"居中窗口时出错: {e}")
            self.move(100, 100)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 创建圆角矩形路径
        path = QPainterPath()
        path.addRoundedRect(self.rect().x(), self.rect().y(), self.rect().width(), self.rect().height(), 10, 10)  # 10px圆角半径
        painter.setClipPath(path)

        # 绘制背景图片
        if self.background and not self.background.isNull():
            painter.drawPixmap(self.rect(), self.background)
        else:
            painter.fillRect(self.rect(), QColor(30, 30, 50, 230))

        super().paintEvent(event)

    def _scale_background_to_window(self):
        """自适应背景图片缩放"""
        if self.original_background and not self.original_background.isNull():
            # 使用KeepAspectRatioByExpanding确保背景填满窗口，可能会裁剪
            self.background = self.original_background.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
        else:
            self.background = QPixmap()

    def resizeEvent(self, event):
        """窗口大小改变事件处理"""
        # 重新缩放背景图片（保持当前背景，不重新加载）
        if self.background and not self.background.isNull():
            # 如果已有背景图片，只需重新缩放
            self._scale_background_to_window()
        else:
            # 如果没有背景图片，尝试加载
            self._load_background()

        # 更新布局比例（保持相对比例不变）
        self._update_layout_proportions()

        # 更新控件高度
        self._update_control_heights()

        # 更新字体大小
        self._apply_responsive_fonts()

        super().resizeEvent(event)

    def _apply_responsive_fonts(self):
        """应用响应式字体大小"""
        window_height = self.height()
        window_width = self.width()

        # 基础字体大小（基于窗口尺寸）
        if window_height < 700:  # 小窗口
            base_font_size = 10
            title_font_size = 18
            button_font_size = 11
            group_title_font_size = 14
            log_font_size = 9
        elif window_height > 1000:  # 大窗口
            base_font_size = 12
            title_font_size = 24
            button_font_size = 14
            group_title_font_size = 17
            log_font_size = 10
        else:  # 中等窗口
            base_font_size = 11
            title_font_size = 20
            button_font_size = 12
            group_title_font_size = 15
            log_font_size = 9

        # 应用字体到各个控件
        if hasattr(self, 'main_widget') and self.main_widget:
            self._set_widget_fonts(self.main_widget, {
                'base_size': base_font_size,
                'title_size': title_font_size,
                'button_size': button_font_size,
                'group_title_size': group_title_font_size,
                'log_size': log_font_size
            })

    def _set_widget_fonts(self, widget, font_sizes):
        """递归设置控件字体"""
        if not widget:
            return

        base_font_size = font_sizes['base_size']
        title_font_size = font_sizes['title_size']
        button_font_size = font_sizes['button_size']
        group_title_font_size = font_sizes['group_title_size']
        log_font_size = font_sizes['log_size']

        # 根据控件类型设置不同字体
        widget_type = type(widget).__name__

        try:
            # 特别处理：对于QGroupBox，需要动态更新样式表
            if widget_type == 'QGroupBox':
                font = QFont(self.custom_font_family, group_title_font_size)
                font.setBold(True)
                widget.setFont(font)
                # 动态更新QGroupBox的样式表以匹配字体大小
                self._update_groupbox_style(widget, group_title_font_size)
            elif widget_type == 'CustomLabel_title':
                font = QFont(self.custom_font_family, title_font_size)
                font.setBold(True)
                widget.setFont(font)
            elif widget_type == 'QPushButton':
                if hasattr(widget, 'objectName'):
                    obj_name = widget.objectName()
                    if obj_name == 'startButton':
                        font = QFont(self.custom_font_family, button_font_size + 2, QFont.Weight.Bold)
                    elif obj_name in ['minButton', 'closeButton']:
                        font = QFont('Arial', button_font_size - 1, QFont.Weight.Bold)
                    elif obj_name in ['browseButton', 'freeButton']:
                        font = QFont(self.custom_font_family, button_font_size - 1)
                    else:
                        font = QFont(self.custom_font_family, button_font_size)
                    widget.setFont(font)
            elif widget_type == 'QGroupBox':
                font = QFont(self.custom_font_family, group_title_font_size)
                font.setBold(True)
                widget.setFont(font)
            elif widget_type == 'CustomLabel':
                if hasattr(widget, 'text') and widget.text() and ':' in widget.text():
                    # 标签文字
                    font = QFont(self.custom_font_family, base_font_size, QFont.Weight.Bold)
                    widget.setFont(font)
                else:
                    font = QFont(self.custom_font_family, base_font_size)
                    widget.setFont(font)
            elif widget_type == 'QLineEdit':
                font = QFont(self.custom_font_family, base_font_size)
                widget.setFont(font)
            elif widget_type == 'QComboBox':
                font = QFont(self.custom_font_family, base_font_size)
                widget.setFont(font)
            elif widget_type == 'QCheckBox':
                font = QFont(self.custom_font_family, base_font_size, QFont.Weight.Bold)
                widget.setFont(font)
            elif widget_type == 'QTextEdit' and hasattr(widget, 'objectName') and widget.objectName() == 'logArea':
                font = QFont(self.custom_font_family, log_font_size)
                widget.setFont(font)
            else:
                # 默认字体
                font = QFont(self.custom_font_family, base_font_size)
                widget.setFont(font)
        except Exception as e:
            print(f"设置字体失败 {widget_type}: {e}")

        # 递归处理子控件
        if hasattr(widget, 'children'):
            for child in widget.children():
                if hasattr(child, 'setFont'):
                    self._set_widget_fonts(child, font_sizes)

    def _get_responsive_control_height(self, window_height, control_type='input'):
        """获取响应式控件高度"""
        if window_height < 700:  # 小窗口
            if control_type == 'input':
                return max(24, int(window_height * 0.035))  # 输入框高度
            elif control_type == 'button':
                return max(28, int(window_height * 0.045))  # 按钮高度
            elif control_type == 'combo':
                return max(24, int(window_height * 0.035))  # 下拉框高度
        elif window_height > 1000:  # 大窗口
            if control_type == 'input':
                return max(32, int(window_height * 0.04))
            elif control_type == 'button':
                return max(40, int(window_height * 0.05))
            elif control_type == 'combo':
                return max(32, int(window_height * 0.04))
        else:  # 中等窗口
            if control_type == 'input':
                return max(28, int(window_height * 0.038))
            elif control_type == 'button':
                return max(35, int(window_height * 0.048))
            elif control_type == 'combo':
                return max(28, int(window_height * 0.038))

    def _update_control_heights(self):
        """简化控件高度更新"""
        pass

    def _update_layout_proportions(self):
        """更新布局比例，保持各区域相对比例不变"""
        if not hasattr(self, 'main_widget') or not self.main_widget:
            return

        # 获取当前窗口尺寸
        window_width = self.width()
        window_height = self.height()

        # 定义相对比例（这些比例可以根据背景图片尺寸动态调整）
        # 基础比例配置
        base_proportions = {
            'title_bar': 0.12,      # 标题栏占比
            'api_group': 0.20,      # API设置区域
            'file_group': 0.18,     # 文件选择区域
            'export_group': 0.18,   # 导出控制区域
            'log_group': 0.32,      # 日志区域
            'spacing': 0.02         # 间距占比
        }

        # 根据窗口尺寸调整比例（响应式设计）
        if window_height < 700:  # 小窗口
            proportions = {
                'title_bar': 0.08,      # 减小标题栏占比
                'api_group': 0.15,      # 减小API区域
                'file_group': 0.13,     # 减小文件区域
                'export_group': 0.13,   # 减小导出区域
                'log_group': 0.45,      # 增大日志区域
                'spacing': 0.01         # 减小间距
            }
        elif window_height > 1000:  # 大窗口
            proportions = {
                'title_bar': 0.08,
                'api_group': 0.22,
                'file_group': 0.20,
                'export_group': 0.20,
                'log_group': 0.28,
                'spacing': 0.02
            }
        else:
            proportions = base_proportions

        # 更新主布局的边距和间距
        if hasattr(self, 'main_widget') and self.main_widget.layout():
            main_layout = self.main_widget.layout()

            # 动态调整边距（基于窗口尺寸）
            if window_height < 700:  # 小窗口使用更小边距
                margin_size = max(10, min(25, int(window_width * 0.02)))
            else:
                margin_size = max(15, min(40, int(window_width * 0.025)))
            main_layout.setContentsMargins(margin_size, margin_size, margin_size, margin_size)

            # 动态调整间距
            if window_height < 700:  # 小窗口使用更小间距
                spacing_size = max(5, min(15, int(window_height * 0.015)))
            else:
                spacing_size = max(10, min(25, int(window_height * 0.02)))
            main_layout.setSpacing(spacing_size)

        # 更新内容区域的布局权重
        if hasattr(self, 'content_widget') and self.content_widget:
            content_layout = self.content_widget.layout()
            if content_layout:
                # 重新设置各组的拉伸因子
                for i in range(content_layout.count()):
                    item = content_layout.itemAt(i)
                    if item and item.widget():
                        widget = item.widget()
                        if hasattr(widget, 'objectName'):
                            obj_name = widget.objectName()
                            if obj_name == 'apiGroup':
                                stretch_factor = int(proportions['api_group'] * 100)
                            elif obj_name == 'fileGroup':
                                stretch_factor = int(proportions['file_group'] * 100)
                            elif obj_name == 'exportGroup':
                                stretch_factor = int(proportions['export_group'] * 100)
                            elif obj_name == 'logGroup':
                                stretch_factor = int(proportions['log_group'] * 100)
                            else:
                                stretch_factor = 10

                            content_layout.setStretch(i, stretch_factor)

    def _update_input_mode_ui(self):
        """根据当前的输入模式更新UI元素的启用/禁用状态"""
        if not self.json_path_entry or not self.json_browse_button or not self.json_format_combo:
            return

        if self._current_input_mode in ["free_transcription", "cloud_transcription"]:
            self.json_path_entry.setEnabled(False)
            self.json_browse_button.setEnabled(False)
            self.json_format_combo.setEnabled(False)

            if self._current_input_mode == "free_transcription":
                self.json_path_entry.setPlaceholderText("通过'免费转录'模式提供音频文件")
                button_text = "取消免费转录"
            elif self._current_input_mode == "cloud_transcription":
                # 进一步区分是免费ElevenLabs还是付费服务
                if (hasattr(self, 'cloud_transcription_settings') and
                    self.cloud_transcription_settings.get('provider') == 'elevenlabs_api'):
                    self.json_path_entry.setPlaceholderText("通过'付费ElevenLabs'模式提供音频文件")
                    button_text = "取消云端转录"
                else:
                    self.json_path_entry.setPlaceholderText("通过'云端转录'模式提供音频文件")
                    button_text = "取消云端转录"

            # 更新按钮文本为取消模式
            if self.free_transcription_button:
                self.free_transcription_button.setText(button_text)
                self.free_transcription_button.setProperty("cancelMode", True)
                self.free_transcription_button.style().unpolish(self.free_transcription_button)
                self.free_transcription_button.style().polish(self.free_transcription_button)
                self._free_transcription_button_is_in_cancel_mode = True

            elevenlabs_index = self.json_format_combo.findText("ElevenLabs(推荐)")
            if elevenlabs_index != -1:
                self.json_format_combo.setCurrentIndex(elevenlabs_index)
        else: # local_json mode
            self.json_path_entry.setEnabled(True)
            self.json_browse_button.setEnabled(True)
            self.json_format_combo.setEnabled(True)
            self.json_path_entry.setPlaceholderText("选择包含ASR结果的 JSON 文件")

            # 新增：恢复按钮文本为正常模式
            if self.free_transcription_button:
                self.free_transcription_button.setText("云端获取JSON")
                self.free_transcription_button.setProperty("cancelMode", False)
                self.free_transcription_button.style().unpolish(self.free_transcription_button)
                self.free_transcription_button.style().polish(self.free_transcription_button)
                self._free_transcription_button_is_in_cancel_mode = False

            last_format = self.config.get('last_source_format', 'ElevenLabs(推荐)')
            last_format_index = self.json_format_combo.findText(last_format)
            if last_format_index != -1:
                 self.json_format_combo.setCurrentIndex(last_format_index)

        # 更新AI纠错复选框状态
        self._on_format_changed()

    def _on_format_changed(self):
        """当JSON格式变化时，控制AI纠错复选框的状态"""
        if not self.ai_correction_check or not self.json_format_combo:
            return

        current_format = self.json_format_combo.currentText()
        is_soniox = "Soniox" in current_format

        if is_soniox:
            # Soniox格式：启用复选框
            self.ai_correction_check.setEnabled(True)
            self.ai_correction_check.setToolTip("Soniox格式支持AI错词校对，会消耗Token")
        else:
            # 非Soniox格式：禁用复选框
            self.ai_correction_check.setEnabled(False)
            self.ai_correction_check.setChecked(False)  # 切换格式时自动取消勾选
            self.ai_correction_check.setToolTip("AI错词校对仅支持Soniox格式")

    def init_ui(self):
        # 设置窗口样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f8f8;
            }
            QWidget#centralWidget {
                background-color: #f8f8f8;
            }
        """)

        main_layout = QVBoxLayout(self.main_widget)
        main_layout.setContentsMargins(25,25,25,25)
        main_layout.setSpacing(20)
        # 应用响应式字体
        window_height = self.height()
        if window_height < 700:  # 小窗口
            base_font_size = 10
        elif window_height > 1000:  # 大窗口
            base_font_size = 12
        else:  # 中等窗口
            base_font_size = 11

        # 设置默认字体族名，避免属性访问错误
        self.custom_font_family = "Microsoft YaHei"
        self.base_font_size = base_font_size

        # 立即加载自定义字体
        self._load_custom_font_delayed()

        title_bar_layout = QHBoxLayout()
        
        # SRT高级参数设置按钮
        self.settings_button = QPushButton()
        settings_icon_path_str = resource_path("settings_icon.png")
        button_size = 38
        if settings_icon_path_str and os.path.exists(settings_icon_path_str):
            self.settings_button.setIcon(QIcon(settings_icon_path_str))
            icon_padding = 8
            calculated_icon_dim = max(1, button_size - icon_padding)
            self.settings_button.setIconSize(QSize(calculated_icon_dim, calculated_icon_dim))
        else:
            self.settings_button.setText("⚙S")
            self._early_log("警告: 设置图标 'settings_icon.png' 未找到。")
        
        self.settings_button.setFixedSize(button_size, button_size)
        self.settings_button.setObjectName("settingsButton")
        self.settings_button.setToolTip("自定义高级SRT参数")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        title_bar_layout.addWidget(self.settings_button)

        # LLM 高级设置按钮
        self.llm_advanced_settings_button = QPushButton()
        llm_icon_path_str = resource_path("llm_setting_icon.png")
        if llm_icon_path_str and os.path.exists(llm_icon_path_str):
            self.llm_advanced_settings_button.setIcon(QIcon(llm_icon_path_str))
            icon_padding = 8
            calculated_icon_dim = max(1, button_size - icon_padding)
            self.llm_advanced_settings_button.setIconSize(QSize(calculated_icon_dim, calculated_icon_dim))
        else:
            self.llm_advanced_settings_button.setText("⚙L")
            self._early_log(f"警告: LLM 设置图标 'llm_setting_icon.png' 未找到于 {llm_icon_path_str}")
        
        self.llm_advanced_settings_button.setFixedSize(button_size, button_size)
        self.llm_advanced_settings_button.setObjectName("llmSettingsButton")
        self.llm_advanced_settings_button.setToolTip("LLM高级设置 (API地址, 模型, 温度等)")
        self.llm_advanced_settings_button.clicked.connect(self.open_llm_advanced_settings_dialog)
        title_bar_layout.addWidget(self.llm_advanced_settings_button)

        # 背景设置按钮
        self.background_settings_button = QPushButton()
        background_settings_icon_path_str = resource_path("background_settings_icon.png")
        if background_settings_icon_path_str and os.path.exists(background_settings_icon_path_str):
            self.background_settings_button.setIcon(QIcon(background_settings_icon_path_str))
            icon_padding = 8
            calculated_icon_dim = max(1, button_size - icon_padding)
            self.background_settings_button.setIconSize(QSize(calculated_icon_dim, calculated_icon_dim))
        else:
            self.background_settings_button.setText("⚙B")
            self._early_log("警告: 背景设置图标 'background_settings_icon.png' 未找到。")

        self.background_settings_button.setFixedSize(button_size, button_size)
        self.background_settings_button.setObjectName("backgroundSettingsButton")
        self.background_settings_button.setToolTip("背景设置 (随机背景、自定义文件夹等)")
        self.background_settings_button.clicked.connect(self.open_background_settings_dialog)
        title_bar_layout.addWidget(self.background_settings_button)

        title = CustomLabel_title("Heal-Jimaku (治幕)")
        title_font = QFont(self.custom_font_family, 23)  # 从24pt减小到23pt
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        control_btn_layout = QHBoxLayout()
        control_btn_layout.setSpacing(10)
        min_btn = QPushButton("─")
        min_btn.setFixedSize(30,30)
        min_btn.setObjectName("minButton")
        min_btn.clicked.connect(self.showMinimized)
        min_btn.setToolTip("最小化")

        close_btn = QPushButton("×")
        close_btn.setFixedSize(30,30)
        close_btn.setObjectName("closeButton")
        close_btn.clicked.connect(self.close_application)
        close_btn.setToolTip("关闭")

        control_btn_layout.addWidget(min_btn)
        control_btn_layout.addWidget(close_btn)

        title_bar_layout.addStretch(1)
        title_bar_layout.addWidget(title,2,Qt.AlignmentFlag.AlignCenter)
        title_bar_layout.addStretch(1)
        title_bar_layout.addLayout(control_btn_layout)
        main_layout.addLayout(title_bar_layout)
        main_layout.addSpacing(20)

        content_widget = TransparentWidget(bg_color=QColor(191,191,191,50))
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(25,25,40,25)  # 右侧留40px给滚动条（25+15）
        content_layout.setSpacing(15)

        api_group = QGroupBox("大模型 API KEY 设置(默认请输入ds官key)")
        api_group.setObjectName("apiGroup")
        api_layout = QVBoxLayout(api_group)
        api_layout.setSpacing(12)
        api_key_layout = QHBoxLayout()
        api_label = CustomLabel("API Key:")
        api_label.setFont(QFont(self.custom_font_family, 13, QFont.Weight.Bold))

        # API Key输入布局
        api_key_input_layout = QHBoxLayout()
        api_key_input_layout.setSpacing(0)

        self.api_key_entry = QLineEdit()
        self.api_key_entry.setPlaceholderText("在此输入 API Key (详情请见LLM高级设置)")
        self.api_key_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_entry.setObjectName("apiKeyEdit")

        # 为API Key输入框添加右侧内边距，为眼睛按钮留出空间
        # 注意：这个样式会在后面与全局样式合并
        self.api_key_entry.setStyleSheet("QLineEdit#apiKeyEdit { padding-right: 40px; }")

        # 创建显示/隐藏密码按钮
        self.api_key_visibility_button = QPushButton()
        self.api_key_visibility_button.setFixedSize(20, 20)
        self.api_key_visibility_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.api_key_visibility_button.setToolTip("显示 API Key")
        self.api_key_visibility_button.setObjectName("apiKeyVisibilityButton")

        # 加载眼睛图标
        eye_invisible_path = resource_path("eye-Invisible.png")
        eye_visible_path = resource_path("eye-Visible.png")

        # 加载并缩放图标（从90x90缩放到16x16）
        if os.path.exists(eye_invisible_path):
            eye_invisible_pixmap = QPixmap(eye_invisible_path)
            eye_invisible_icon = QIcon(eye_invisible_pixmap.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.api_key_visibility_button.setIcon(eye_invisible_icon)
            self.api_key_visibility_button.setIconSize(QSize(16, 16))
        else:
            self.api_key_visibility_button.setText("👁")

        self.api_key_visibility_button.setStyleSheet("""
            QPushButton#apiKeyVisibilityButton {
                border: none;
                background: transparent;
                padding: 0px;
                margin: 0px;
                border-radius: 2px;
            }
            QPushButton#apiKeyVisibilityButton:hover {
                background: rgba(255, 255, 255, 0.15);
                border: none;
            }
            QPushButton#apiKeyVisibilityButton:pressed {
                background: rgba(255, 255, 255, 0.25);
                border: none;
            }
        """)

        # 存储图标路径供后续使用
        self.eye_invisible_path = eye_invisible_path
        self.eye_visible_path = eye_visible_path

        # 连接点击事件
        self.api_key_visibility_button.clicked.connect(self.toggle_api_key_visibility)

        # 创建一个容器来放置输入框和眼睛按钮
        api_key_input_container = QWidget()
        api_key_input_container.setMinimumHeight(35)
        api_key_input_layout = QHBoxLayout(api_key_input_container)
        api_key_input_layout.setContentsMargins(0, 0, 0, 0)
        api_key_input_layout.setSpacing(0)

        # 添加输入框
        api_key_input_layout.addWidget(self.api_key_entry)

        # 在右侧添加眼睛按钮
        # 减少负间距，让眼睛按钮正确叠加在边框内的留白区域
        api_key_input_layout.addSpacing(-38)  # 调整负间距以适应增加的右边距
        api_key_input_layout.addWidget(self.api_key_visibility_button, 0, Qt.AlignmentFlag.AlignVCenter)

        api_key_layout.addWidget(api_label)
        api_key_layout.addWidget(api_key_input_container)
        api_layout.addLayout(api_key_layout)

        # 创建一个水平布局来放置复选框和测试连接按钮
        test_button_layout = QHBoxLayout()

        # 将"记住API Key"复选框放在最左侧
        self.remember_api_key_checkbox = StrokeCheckBoxWidget("记住 API Key")
        # 设置字体以匹配主窗口
        if hasattr(self, 'custom_font_family'):
            self.remember_api_key_checkbox.label.setStyleSheet(
                f"background-color: transparent; font-size: 12pt; font-family: '{self.custom_font_family}'; font-weight: bold;"
            )
        self.remember_api_key_checkbox.setToolTip("勾选后，本次输入的API Key将被保存，下次启动时自动填充")
        self.remember_api_key_checkbox.setChecked(False)  # 默认不记住
        # 复选框状态将在后面的初始化阶段设置，避免重复设置
        # 这里先保持默认状态（不勾选）

        # StrokeCheckBoxWidget已经内置了描边效果，无需额外设置样式表

        # 连接复选框状态变化信号
        self.remember_api_key_checkbox.toggled.connect(self._on_remember_api_key_toggled)

        # 连接API Key输入框变化信号
        self.api_key_entry.textChanged.connect(self._on_api_key_text_changed)

        # 复选框放在最左侧
        test_button_layout.addWidget(self.remember_api_key_checkbox, 0)

        # 添加弹性空间，将测试连接按钮推到右边
        test_button_layout.addStretch()

        # 添加一些间距
        test_button_layout.addSpacing(10)

        # 添加测试连接按钮
        self.test_connection_button = QPushButton("🔗 测试当前配置连接")
        self.test_connection_button.setToolTip("测试当前LLM配置的连接状态")
        self.test_connection_button.setObjectName("testConnectionButton")
        self.test_connection_button.clicked.connect(self.test_llm_connection_from_main)
        self.test_connection_button.setFixedWidth(150)  # 增加宽度以适应更长的文本

        test_button_layout.addWidget(self.test_connection_button, 0)  # 按钮不拉伸
        api_layout.addLayout(test_button_layout)

        file_group = QGroupBox("文件选择")
        file_group.setObjectName("fileGroup")
        file_layout = QVBoxLayout(file_group)
        file_layout.setSpacing(12)
        
        json_input_line_layout = QHBoxLayout()
        json_input_line_layout.setSpacing(5)  # 减小间距到5px

        json_label = CustomLabel("JSON 文件:")
        json_label.setFont(QFont(self.custom_font_family, 13, QFont.Weight.Bold))
        json_input_line_layout.addWidget(json_label, 0)  # 标签不拉伸

        self.json_path_entry = QLineEdit()
        self.json_path_entry.setPlaceholderText("选择包含ASR结果的 JSON 文件")
        self.json_path_entry.setObjectName("pathEdit")
        json_input_line_layout.addWidget(self.json_path_entry, 1)  # 输入框占主要空间

        self.json_browse_button = QPushButton("浏览...")
        self.json_browse_button.setObjectName("browseButton")
        self.json_browse_button.clicked.connect(self.browse_json_file)
        self.json_browse_button.setFixedWidth(100)  # 与导出区域按钮保持一致
        json_input_line_layout.addWidget(self.json_browse_button, 0)  # 按钮不拉伸

        self.free_transcription_button = QPushButton("云端获取JSON")
        self.free_transcription_button.setObjectName("freeButton")
        self.free_transcription_button.clicked.connect(self.handle_free_transcription_button_click)
        self.free_transcription_button.setFixedWidth(100)  # 与导出区域按钮保持一致
        json_input_line_layout.addWidget(self.free_transcription_button, 0)  # 按钮不拉伸

        file_layout.addLayout(json_input_line_layout)

        format_layout = QHBoxLayout()
        format_layout.setSpacing(5)  # 减小间距到5px
        format_label = CustomLabel("JSON 格式:")
        format_label.setFont(QFont(self.custom_font_family, 13, QFont.Weight.Bold))
        self.json_format_combo = QComboBox()
        self.json_format_combo.addItems(["ElevenLabs(推荐)", "Soniox(推荐)", "Whisper(推荐)", "Deepgram", "AssemblyAI"])
        self.json_format_combo.setObjectName("formatCombo")

        # 监听格式变化以控制AI纠错复选框
        self.json_format_combo.currentTextChanged.connect(self._on_format_changed)

        # 设置字体大小并调整下拉框尺寸
        combo_font = QFont(self.custom_font_family, 16)  # 进一步放大字体到16px
        combo_font.setBold(True)  # 加粗显示
        self.json_format_combo.setFont(combo_font)

        # 调整下拉框的样式，与JSON文件输入框高度一致，并明确指定字体大小
        self.json_format_combo.setStyleSheet("""
            QComboBox {
                min-height: 1.8em;  /* 与pathEdit输入框高度一致 */
                padding: 6px;  /* 与pathEdit输入框内边距一致 */
                font-size: 16px;  /* 明确指定字体大小 */
                font-weight: bold;  /* 加粗显示 */
            }
            QComboBox QAbstractItemView {
                font-size: 16px;  /* 下拉列表项字体大小 */
                font-weight: bold;  /* 加粗显示 */
                min-height: 1.8em;  /* 列表项高度也与输入框一致 */
                padding: 6px;  /* 列表项内边距 */
            }
        """)

        format_layout.addWidget(format_label, 0)  # 标签不拉伸
        format_layout.addWidget(self.json_format_combo, 1)  # 下拉框占主要空间

        # 添加AI纠错复选框在格式选择右侧
        self.ai_correction_check = StrokeCheckBoxWidget("启用AI错词校对")
        self.ai_correction_check.setChecked(False)  # 默认不勾选
        self.ai_correction_check.setToolTip("仅对Soniox格式的JSON文件有效，会消耗Token进行AI纠错")
        format_layout.addWidget(self.ai_correction_check, 0)  # 复选框不拉伸

        file_layout.addLayout(format_layout)

        export_group = QGroupBox("导出与控制")
        export_group.setObjectName("exportGroup")
        export_layout = QVBoxLayout(export_group)
        export_layout.setSpacing(12)
        output_layout = QHBoxLayout()
        output_layout.setSpacing(5)  # 减小间距到5px
        output_label = CustomLabel("导出目录:")
        output_label.setFont(QFont(self.custom_font_family, 13, QFont.Weight.Bold))
        self.output_path_entry = QLineEdit()
        self.output_path_entry.setPlaceholderText("选择 SRT 文件保存目录")
        self.output_path_entry.setObjectName("pathEdit")
        self.output_browse_button = QPushButton("浏览...")
        self.output_browse_button.setObjectName("browseButton")
        self.output_browse_button.clicked.connect(self.select_output_dir)
        # 统一按钮长度，与"云端转录"按钮保持一致
        self.output_browse_button.setFixedWidth(100)  # 设置固定宽度
        output_layout.addWidget(output_label, 0)  # 标签不拉伸
        output_layout.addWidget(self.output_path_entry, 1)  # 输入框占主要空间
        output_layout.addWidget(self.output_browse_button, 0)  # 按钮不拉伸
        export_layout.addLayout(output_layout)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setObjectName("progressBar")
        export_layout.addWidget(self.progress_bar)
        
        self.start_button = QPushButton("开始转换")
        self.start_button.setFixedHeight(45)
        self.start_button.setFont(QFont('楷体', 14, QFont.Weight.Bold))
        self.start_button.setObjectName("startButton")
        self.start_button.clicked.connect(self.start_conversion)
        # 设置默认样式（蓝色）
        self.start_button.setStyleSheet(self._get_default_start_btn_style())
        export_layout.addWidget(self.start_button)

        log_group = QGroupBox("日志")
        log_group.setObjectName("logGroup")
        log_layout = QVBoxLayout(log_group)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setObjectName("logArea")
        log_layout.addWidget(self.log_area)

        # 使用自适应布局权重（替代固定的硬编码比例）
        # 初始权重基于窗口尺寸计算
        window_height = self.height()

        # 根据窗口高度动态调整初始权重
        if window_height < 864:  # 小窗口（调整后的最小高度）
            api_weight = 16
            file_weight = 14
            export_weight = 27  # 增加导出区域占比，从日志区域拿
            log_weight = 27  # 减少日志区域占比
        elif window_height > 1000:  # 大窗口
            api_weight = 22
            file_weight = 20
            export_weight = 25  # 增加导出区域占比
            log_weight = 25  # 减少日志区域占比
        else:  # 中等窗口
            api_weight = 20
            file_weight = 18
            export_weight = 26  # 增加导出区域占比
            log_weight = 26  # 减少日志区域占比

        content_layout.addWidget(api_group, api_weight)
        content_layout.addWidget(file_group, file_weight)
        content_layout.addWidget(export_group, export_weight)
        content_layout.addWidget(log_group, log_weight)

        # === 修改开始：添加滚动区域 ===
        # 创建滚动区域作为保护层
        scroll_area = QScrollArea()
        scroll_area.setWidget(content_widget)
        scroll_area.setWidgetResizable(True)  # 关键：让内部控件自适应宽度
        
        # 美化滚动区域：让它透明且无边框，看起来像没加一样自然
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)
        
        # 策略：垂直方向按需显示滚动条，水平方向永远关闭
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 把滚动区域加到主布局里，而不是直接加 content_widget
        main_layout.addWidget(scroll_area, 1)
        # === 修改结束 ===
        
        self._update_input_mode_ui()
        self.apply_styles()

        # 应用响应式字体大小
        self._apply_responsive_fonts()

        # 更新控件高度
        self._update_control_heights()

    def _init_adaptive_window_size(self):
        """初始化自适应窗口尺寸"""
        # 获取屏幕尺寸
        screen = QApplication.primaryScreen()
        if not screen:
            # 如果无法获取屏幕信息，使用默认尺寸
            self.resize(1024, 864)
            return

        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        # 获取背景图片尺寸 - 根据当前背景设置
        bg_path_str = None
        if hasattr(self, 'background_settings') and hasattr(self, 'background_manager'):
            if not self.background_settings.get('enable_random', True):
                # 固定背景模式
                fixed_path = self.background_settings.get('fixed_background_path', '')
                if fixed_path and os.path.exists(fixed_path):
                    bg_path_str = fixed_path
            else:
                # 随机背景模式 - 使用已加载的背景路径
                if self.background_manager.last_background_path and os.path.exists(self.background_manager.last_background_path):
                    bg_path_str = self.background_manager.last_background_path

        # 如果没有指定背景路径，使用默认背景
        if not bg_path_str:
            default_bg_path = resource_path("background.png")
            if default_bg_path and os.path.exists(default_bg_path):
                bg_path_str = default_bg_path
            else:
                # 如果默认background.png不存在，使用默认尺寸
                bg_path_str = None

        bg_width, bg_height = self._get_background_image_size(bg_path_str)

        # 计算基础窗口尺寸（基于背景图片或默认值）
        if bg_width > 0 and bg_height > 0:
            # 使用背景图片尺寸作为基础
            base_width = bg_width
            base_height = bg_height
        else:
            # 使用默认尺寸
            base_width = 1024
            base_height = 864

        # 计算合适的窗口尺寸（考虑屏幕限制）
        # 留出一些边距，不要超过屏幕的90%
        max_allowed_width = int(screen_width * 0.9)
        max_allowed_height = int(screen_height * 0.9)

        # 设置最小和最大尺寸约束 - 有了滚动条兜底，可以大胆降低最小高度
        min_width = 960   # 稍微降低宽度限制
        min_height = 600  # 直接降到 600！
        
        # 双保险：如果检测到屏幕真的很小，就进一步放宽
        if screen_height < 900:
            min_height = 550  # 给 1080P 150% 缩放留足余地
            self._log_early(f"检测到小屏幕 ({screen_height}px)，最小高度调整为 {min_height}px")
        
        max_width = max_allowed_width
        max_height = max_allowed_height

        # 计算最终尺寸
        final_width = max(min_width, min(base_width, max_width))
        final_height = max(min_height, min(base_height, max_height))

        # 如果背景图片太大，按比例缩放
        if base_width > max_allowed_width or base_height > max_allowed_height:
            # 计算缩放比例
            width_ratio = max_allowed_width / base_width
            height_ratio = max_allowed_height / base_height
            scale_ratio = min(width_ratio, height_ratio, 1.0)  # 不要放大

            final_width = int(base_width * scale_ratio)
            final_height = int(base_height * scale_ratio)

        # 应用计算出的尺寸
        self.resize(final_width, final_height)

        # 设置最小和最大尺寸约束
        self.setMinimumSize(min_width, min_height)
        self.setMaximumSize(max_width, max_height)

        self._log_early(f"窗口尺寸自适应: {final_width}x{final_height} (屏幕: {screen_width}x{screen_height})")

    def _get_background_image_size(self, bg_path_str: str) -> tuple[int, int]:
        """获取背景图片的尺寸"""
        if not bg_path_str or not os.path.exists(bg_path_str):
            return (0, 0)

        try:
            pixmap = QPixmap(bg_path_str)
            if pixmap.isNull():
                return (0, 0)
            return (pixmap.width(), pixmap.height())
        except Exception as e:
            self._early_log(f"获取背景图片尺寸失败: {e}")
            return (0, 0)

    def apply_styles(self):
        group_title_red = "#B34A4A"; input_text_red = "#7a1723"; soft_orangebrown_text = "#CB7E47"
        button_blue_bg = "rgba(100, 149, 237, 190)"; button_blue_hover = "rgba(80, 129, 217, 220)"
        control_min_blue = "rgba(135, 206, 235, 180)"; control_min_hover = "rgba(110, 180, 210, 220)"
        control_close_red = "rgba(255, 99, 71, 180)"; control_close_hover = "rgba(220, 70, 50, 220)"
        settings_btn_bg = "rgba(120, 120, 150, 180)"; settings_btn_hover = "rgba(100, 100, 130, 210)"
        group_bg = "rgba(52, 129, 184, 30)"
        input_bg = "rgba(255, 255, 255, 30)"; input_hover_bg = "rgba(255, 255, 255, 40)"
        input_focus_bg = "rgba(255, 255, 255, 50)"; input_border_color = "rgba(135, 206, 235, 90)"
        input_focus_border_color = "#87CEEB"
        log_bg = "rgba(0, 0, 0, 55)"; log_text_custom_color = "#E1F5FE"
        combo_dropdown_bg = "rgba(250, 250, 250, 235)"; combo_dropdown_text_color = "#2c3e50"
        combo_dropdown_border_color = "rgba(135, 206, 235, 150)"
        combo_dropdown_selection_bg = button_blue_hover; combo_dropdown_selection_text_color = "#FFFFFF"
        combo_dropdown_hover_bg = "rgba(173, 216, 230, 150)"

        label_green_color = QColor(92, 138, 111).name()

        qss_image_url = ""
        raw_arrow_path = resource_path("dropdown_arrow.png")
        if raw_arrow_path and os.path.exists(raw_arrow_path):
            abs_arrow_path = os.path.abspath(raw_arrow_path)
            formatted_path = abs_arrow_path.replace(os.sep, '/')
            qss_image_url = f"url('{formatted_path}')"
        else:
            self._early_log(f"警告: 下拉箭头图标 'dropdown_arrow.png' 未找到。")

        qss_checkmark_image_url = ""
        raw_checkmark_path = resource_path('checkmark.png')
        if raw_checkmark_path and os.path.exists(raw_checkmark_path):
            abs_checkmark_path = os.path.abspath(raw_checkmark_path)
            formatted_checkmark_path = abs_checkmark_path.replace(os.sep, '/')
            qss_checkmark_image_url = f"url('{formatted_checkmark_path}')"
        else:
            self._early_log(f"警告: 选中标记图标 'checkmark.png' 未找到。")

        free_button_bg = "rgba(100, 180, 120, 190)"; free_button_hover = "rgba(80, 160, 100, 220)"
        # 取消模式的样式
        cancel_button_bg = "rgba(200, 80, 80, 190)"; cancel_button_hover = "rgba(220, 100, 100, 220)"
        # 批量按钮的样式
        batch_button_bg = "rgba(180, 120, 80, 190)"; batch_button_hover = "rgba(160, 100, 60, 220)"

        style = f"""
            QGroupBox {{ font: bold 17pt '{self.custom_font_family}'; border: 1px solid rgba(135,206,235,80); border-radius:8px; margin-top:12px; background-color:{group_bg}; }}
            QGroupBox::title {{ subcontrol-origin:margin; subcontrol-position:top left; left:15px; padding:2px 5px; color:{group_title_red}; font:bold 15pt '{self.custom_font_family}'; }}
            QGroupBox#exportGroup::title {{ subcontrol-origin:padding; subcontrol-position:top left; left:15px; padding:2px 5px; color:{group_title_red}; font:bold 14.7pt '{self.custom_font_family}'; top:-5px; }}
            QGroupBox#apiGroup::title {{ subcontrol-origin:padding; subcontrol-position:top left; left:15px; padding:2px 5px; color:{group_title_red}; font:bold 14.7pt '{self.custom_font_family}'; top:-5px; }}
            QGroupBox#fileGroup::title {{ subcontrol-origin:padding; subcontrol-position:top left; left:15px; padding:2px 5px; color:{group_title_red}; font:bold 14.7pt '{self.custom_font_family}'; top:-5px; }}
            QGroupBox#logGroup::title {{ subcontrol-origin:padding; subcontrol-position:top left; left:15px; padding:2px 5px; color:{group_title_red}; font:bold 14.7pt '{self.custom_font_family}'; top:-5px; }}
            QLineEdit#apiKeyEdit, QLineEdit#pathEdit {{ background-color:{input_bg}; color:{input_text_red}; border:1px solid {input_border_color}; border-radius:5px; padding:6px; font:bold 11pt '{self.custom_font_family}'; min-height:1.8em; }}
            QLineEdit#apiKeyEdit:hover, QLineEdit#pathEdit:hover {{ background-color:{input_hover_bg}; border:1px solid {input_focus_border_color}; }}
        QPushButton#startButton:hover {{ background-color:{input_hover_bg}; }}
            QLineEdit#apiKeyEdit:focus, QLineEdit#pathEdit:focus {{ background-color:{input_focus_bg}; border:1px solid {input_focus_border_color}; }}
            QLineEdit#apiKeyEdit {{ font-family:'Consolas','Courier New',monospace; font-size:12pt; font-weight:bold; }}
            QPushButton#browseButton:hover, QPushButton#startButton:hover {{ background-color:{input_hover_bg}; }}
            QLineEdit#apiKeyEdit:hover, QLineEdit#pathEdit:hover {{ background-color:{input_hover_bg}; border:1px solid {input_focus_border_color}; }}
            QPushButton#browseButton, QPushButton#startButton {{ background-color:{button_blue_bg}; color:white; border:none; border-radius:5px; font-family:'{self.custom_font_family}'; font-weight:bold; }}
            QPushButton#browseButton {{ padding:6px 15px; font-size:10pt; }}
            QPushButton#startButton:hover {{ background-color:{input_hover_bg}; }}
            QPushButton#batchButton {{
                background-color:{batch_button_bg}; color:white; border:none; border-radius:5px;
                font-family:'{self.custom_font_family}'; font-weight:bold; font-size:10pt; padding:6px 15px;
            }}
            QPushButton#batchButton:hover {{ background-color:{batch_button_hover}; }}
            QPushButton#freeButton {{
                background-color:{free_button_bg}; color:white; border:none; border-radius:5px;
                font-family:'{self.custom_font_family}'; font-weight:bold; font-size:10pt; padding:6px 15px;
            }}
            QPushButton#freeButton:hover {{ background-color:{free_button_hover}; }}
            QPushButton#freeButton[cancelMode="true"] {{
                background-color:{cancel_button_bg}; color:white; border:none; border-radius:5px;
                font-family:'{self.custom_font_family}'; font-weight:bold; font-size:10pt; padding:6px 15px;
            }}
            QPushButton#freeButton[cancelMode="true"]:hover {{ background-color:{cancel_button_hover}; }}
            QPushButton#testConnectionButton {{
                background-color:{free_button_bg}; color:white; border:none; border-radius:5px;
                font-family:'{self.custom_font_family}'; font-weight:bold; font-size:10pt; padding:6px 15px;
            }}
            QPushButton#testConnectionButton:hover {{ background-color:{free_button_hover}; }}
            QPushButton#testConnectionButton:disabled {{ background-color:#cccccc; color:#666666; }}
            QPushButton#startButton {{ padding:8px 25px; font:bold 14pt '{self.custom_font_family}'; }}
            QPushButton#batchStartButton {{
                background-color:{batch_button_bg}; color:white; border:none; border-radius:5px;
                padding:8px 25px; font:bold 14pt '{self.custom_font_family}';
            }}
            QPushButton#batchStartButton:hover {{ background-color:{batch_button_hover}; }}
            QPushButton#batchStartButton:disabled {{ background-color:rgba(100,100,100,150); color:#bbbbbb; }}
            QPushButton#browseButton:hover, QPushButton#startButton:hover {{ background-color:{button_blue_hover}; }}
            QPushButton#startButton:disabled {{ background-color:rgba(100,100,100,150); color:#bbbbbb; }}
            QPushButton#minButton {{ background-color:{control_min_blue}; color:white; border:none; border-radius:15px; font-weight:bold; font-size:14pt; }}
            QPushButton#minButton:hover {{ background-color:{control_min_hover}; }}
            QPushButton#closeButton {{ background-color:{control_close_red}; color:white; border:none; border-radius:15px; font-weight:bold; font-size:14pt; }}
            QPushButton#closeButton:hover {{ background-color:{control_close_hover}; }}
            QPushButton#settingsButton, QPushButton#llmSettingsButton, QPushButton#backgroundSettingsButton {{
                background-color:{settings_btn_bg}; color:white;
                border:none; border-radius:19px;
                font-weight:bold; font-size:11pt; padding: 0px;
            }}
            QPushButton#settingsButton:hover, QPushButton#llmSettingsButton:hover, QPushButton#backgroundSettingsButton:hover {{ background-color:{settings_btn_hover}; }}
            QProgressBar#progressBar {{ border:1px solid rgba(135,206,235,80); border-radius:5px; text-align:center; background:rgba(0,0,0,40); height:22px; color:#f0f0f0; font-weight:bold; }}
            QProgressBar#progressBar::chunk {{ background-color:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #5C8A6F,stop:1 #69CFF7); border-radius:5px; }}
            QTextEdit#logArea {{ background-color:{log_bg}; border:1px solid rgba(135,206,235,80); border-radius:5px; color:{log_text_custom_color}; font-family:'{self.custom_font_family}'; font-size:11pt; font-weight:bold;}}
            QComboBox#formatCombo {{
                background-color:{input_bg}; color:{input_text_red};
                border:1px solid {input_border_color}; border-radius:5px;
                padding: 5px 8px 5px 8px;
                font:bold 10pt '{self.custom_font_family}'; min-height:2.8em;
                line-height: 1.4;
            }}
            QComboBox#formatCombo:hover {{ background-color:{input_hover_bg}; border-color:{input_focus_border_color}; }}
            QComboBox#formatCombo:focus {{ background-color:{input_focus_bg}; border-color:{input_focus_border_color}; }}
            QComboBox#formatCombo:on {{ background-color:{input_focus_bg}; border-color:{input_focus_border_color}; padding-right: 8px; }}
            QComboBox#formatCombo::drop-down {{
                subcontrol-origin: padding; subcontrol-position: center right;
                width: 20px; border: none;
            }}
            QComboBox#formatCombo::down-arrow {{
                image: {qss_image_url if qss_image_url else "none"};
                width: 8px; height: 8px;
            }}
            QComboBox QAbstractItemView {{ background-color:{combo_dropdown_bg}; color:{combo_dropdown_text_color}; border:1px solid {combo_dropdown_border_color}; border-radius:5px; padding:4px; outline:0px; }}
            QComboBox QAbstractItemView::item {{ padding:8px 10px; min-height:2.2em; border-radius:3px; background-color:transparent; font-size:10pt; }}
            QComboBox QAbstractItemView::item:selected {{ background-color:{combo_dropdown_selection_bg}; color:{combo_dropdown_selection_text_color}; }}
            QComboBox QAbstractItemView::item:hover {{ background-color:{combo_dropdown_hover_bg}; color:{combo_dropdown_text_color}; }}
            CustomLabel, CustomLabel_title {{ background-color:transparent; }}
            CustomLabel_title {{
                font-family:'{self.custom_font_family}';
                font-size:24pt;
                font-weight:bold;
                padding-top:3px;  /* 增加顶部内边距，避免字符被吞掉 */
                padding-bottom:2px; /* 增加底部内边距，确保字符完整显示 */
            }}
            QLabel {{ background-color:transparent; }}
            """
        self.setStyleSheet(style)

    def _get_source_format_from_combo(self) -> str:
        """
        从UI下拉框获取JSON源格式
        """
        if not self.json_format_combo:
            return "elevenlabs"  # 默认值

        selected_text = self.json_format_combo.currentText()
        source_format_map = {
            "ElevenLabs(推荐)": "elevenlabs",
            "Soniox(推荐)": "soniox",
            "Whisper(推荐)": "whisper",
            "Deepgram": "deepgram",
            "AssemblyAI": "assemblyai"
        }
        return source_format_map.get(selected_text, "elevenlabs")

    def _get_source_format_from_cloud_settings(self):
        """从云端转录设置获取源格式"""
        if not hasattr(self, 'cloud_transcription_settings') or not self.cloud_transcription_settings:
            return "elevenlabs"

        provider = self.cloud_transcription_settings.get('provider', 'elevenlabs_web')
        format_map = {
            'elevenlabs_web': 'elevenlabs',
            'elevenlabs_api': 'elevenlabs_api',
            'soniox_api': 'soniox'
        }
        return format_map.get(provider, 'elevenlabs')

    def log_message(self, message: str, use_user_friendly: bool = True):
        """
        日志记录，支持用户友好的消息转换

        Args:
            message: 要记录的消息
            use_user_friendly: 是否使用用户友好的消息转换（默认True）
        """
        if self.log_area and self.log_area.isVisible():
            # 添加时间戳
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")

            # 使用用户友好的消息转换
            if use_user_friendly:
                formatted_message = user_logger.format_user_message(message)
                # 获取消息级别用于颜色设置
                user_msg, level = user_logger.translate_message(message)
            else:
                # 开发者模式，显示原始消息
                formatted_message = f"[DEV] {message}"

            final_message = f"[{timestamp}] {formatted_message}"

            self.log_area.append(final_message)

            # 保持原来的默认颜色，不进行颜色设置
            # 这样用户体验与旧版一致

            # 滚动到底部
            self.log_area.moveCursor(QTextCursor.MoveOperation.End)
        else:
            if hasattr(self, 'log_area_early_messages'):
                # 早期消息也进行用户友好转换
                if use_user_friendly:
                    formatted_msg = user_logger.format_user_message(message)
                    self.log_area_early_messages.append(formatted_msg)
                else:
                    self.log_area_early_messages.append(message)

            # 控制台输出
            if use_user_friendly:
                formatted_msg = user_logger.format_user_message(message)
                print(f"[用户日志]: {formatted_msg}")
            else:
                print(f"[开发日志]: {message}")

    def log_technical_message(self, message: str):
        """
        记录技术消息（开发者模式）

        Args:
            message: 技术消息
        """
        self.log_message(message, use_user_friendly=False)

    def _apply_log_level_color(self, level: MessageLevel):
        """
        根据消息级别设置文本颜色
        保持与旧版一致的颜色显示

        Args:
            level: 消息级别
        """
        # 注释掉颜色设置，保持原来的默认颜色
        # 这样用户看到的日志颜色与原来一致
        pass

    def handle_error(self, error: Exception, context: str = "", show_user_error: bool = True) -> None:
        """
        统一的错误处理方法

        Args:
            error: 异常对象
            context: 错误上下文描述
            show_user_error: 是否向用户显示错误对话框
        """
        # 生成错误信息
        error_info = f"错误发生在: {context}" if context else "发生错误"
        error_message = f"{error_info}: {str(error)}"
        traceback_str = traceback.format_exc()

        # 记录到用户友好日志
        self.log_message(f"错误: {str(error)}")

        # 记录详细错误到文件（如果配置目录存在）
        try:
            log_file_path = os.path.join(CONFIG_DIR, "error_log.txt")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(log_file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n=== {timestamp} ===\n")
                f.write(f"{error_info}\n")
                f.write(f"错误信息: {str(error)}\n")
                f.write(f"错误类型: {type(error).__name__}\n")
                f.write(f"详细堆栈:\n{traceback_str}\n")
        except Exception as log_error:
            self.log_technical_message(f"记录错误日志失败: {log_error}")

        # 向用户显示友好的错误信息
        if show_user_error:
            self.show_error_to_user(error, context)

    def show_error_to_user(self, error: Exception, context: str = "") -> None:
        """向用户显示友好的错误信息"""
        error_type = type(error).__name__

        # 根据错误类型提供不同的用户友好消息
        friendly_messages = {
            'FileNotFoundError': "找不到指定的文件，请检查文件路径是否正确",
            'PermissionError': "权限不足，请检查文件访问权限",
            'ConnectionError': "网络连接错误，请检查网络连接",
            'TimeoutError': "操作超时，请稍后重试",
            'MemoryError': "内存不足，请关闭其他程序后重试",
            'OSError': "系统错误，请检查文件系统和磁盘空间",
        }

        friendly_msg = friendly_messages.get(error_type, "发生未知错误")

        if context:
            full_message = f"{context}\n\n{friendly_msg}\n\n详细信息: {str(error)}"
        else:
            full_message = f"{friendly_msg}\n\n详细信息: {str(error)}"

        QMessageBox.critical(self, "错误", full_message)

    def load_config(self):
        """优化后的配置加载，添加性能改进和错误处理"""
        if not os.path.exists(CONFIG_DIR):
            try:
                os.makedirs(CONFIG_DIR)
            except OSError as e:
                self._early_log(f"创建配置目录失败: {e}"); return

        default_cfg_structure = {
            'deepseek_api_key': "",
            'remember_api_key': True,
            'last_json_path': '',
            'last_output_path': '',
            'last_source_format': 'ElevenLabs(推荐)',
            'last_input_mode': 'local_json', # Default initial mode
            'last_free_transcription_audio_path': None,
            USER_MIN_DURATION_TARGET_KEY: DEFAULT_MIN_DURATION_TARGET,
            USER_MAX_DURATION_KEY: DEFAULT_MAX_DURATION,
            USER_MAX_CHARS_PER_LINE_KEY: DEFAULT_MAX_CHARS_PER_LINE,
            USER_DEFAULT_GAP_MS_KEY: DEFAULT_DEFAULT_GAP_MS,
            USER_FREE_TRANSCRIPTION_LANGUAGE_KEY: DEFAULT_FREE_TRANSCRIPTION_LANGUAGE,
            USER_FREE_TRANSCRIPTION_NUM_SPEAKERS_KEY: DEFAULT_FREE_TRANSCRIPTION_NUM_SPEAKERS,
            USER_FREE_TRANSCRIPTION_TAG_AUDIO_EVENTS_KEY: DEFAULT_FREE_TRANSCRIPTION_TAG_AUDIO_EVENTS,
            USER_LLM_API_BASE_URL_KEY: DEFAULT_LLM_API_BASE_URL,
            USER_LLM_MODEL_NAME_KEY: DEFAULT_LLM_MODEL_NAME,
            USER_LLM_API_KEY_KEY: DEFAULT_LLM_API_KEY,
            USER_LLM_REMEMBER_API_KEY_KEY: DEFAULT_LLM_REMEMBER_API_KEY,
            USER_LLM_TEMPERATURE_KEY: DEFAULT_LLM_TEMPERATURE,
            app_config.USER_ENABLE_AI_CORRECTION_KEY: app_config.DEFAULT_ENABLE_AI_CORRECTION,
            USER_ENABLE_RANDOM_BACKGROUND_KEY: DEFAULT_ENABLE_RANDOM_BACKGROUND,
            USER_CUSTOM_BACKGROUND_FOLDER_KEY: DEFAULT_CUSTOM_BACKGROUND_FOLDER,
        }

        try:
            # 优化：先检查文件大小，避免加载过大文件
            if os.path.exists(CONFIG_FILE):
                file_size = os.path.getsize(CONFIG_FILE)
                if file_size > 1024 * 1024:  # 1MB限制，防止异常大文件
                    self._early_log("配置文件过大，使用默认配置")
                    self.config = default_cfg_structure.copy()
                else:
                    # 使用更高效的JSON加载
                    with open(CONFIG_FILE, 'r', encoding='utf-8', buffering=8192) as f:
                        loaded_config = json.load(f)
                    self.config = default_cfg_structure.copy()
                    self.config.update(loaded_config)
            else:
                self.config = default_cfg_structure.copy()

            # 向后兼容性处理
            if not self.config.get(USER_LLM_API_KEY_KEY) and self.config.get('deepseek_api_key'):
                self.config[USER_LLM_API_KEY_KEY] = self.config['deepseek_api_key']
            if self.config.get('remember_api_key') is not None:
                 self.config[USER_LLM_REMEMBER_API_KEY_KEY] = self.config['remember_api_key']

            # 确保配置列表存在
            profiles = self.config.get(LLM_PROFILES_KEY, {}).get("profiles", [])
            
            # 如果配置列表为空，创建默认的DeepSeek配置
            if not profiles:
                default_profile = {
                    "id": DEFAULT_CURRENT_PROFILE_ID,
                    "name": "DeepSeek",
                    "provider": app_config.PROVIDER_DEEPSEEK,
                    "api_base_url": app_config.DEFAULT_LLM_API_BASE_URL,
                    "model_name": app_config.DEFAULT_LLM_MODEL_NAME,
                    "api_key": "",
                    "temperature": app_config.DEFAULT_LLM_TEMPERATURE,
                    "is_default": True,
                    "custom_headers": {},
                    "api_format": app_config.API_FORMAT_OPENAI
                }
                profiles.append(default_profile)
                self.config[LLM_PROFILES_KEY] = {"profiles": profiles}
                self.config[CURRENT_PROFILE_ID_KEY] = DEFAULT_CURRENT_PROFILE_ID
            else:
                # 确保至少有一个配置被标记为默认
                has_default = any(p.get("is_default", False) for p in profiles)
                if not has_default and profiles:
                    # 将第一个配置设为默认
                    profiles[0]["is_default"] = True
                    self.config[LLM_PROFILES_KEY] = {"profiles": profiles}
                
                # 确保当前配置ID存在且有效
                current_profile_id = self.config.get(CURRENT_PROFILE_ID_KEY)
                profile_ids = [p.get("id") for p in profiles]
                
                if not current_profile_id or current_profile_id not in profile_ids:
                    # 如果当前配置ID无效，使用默认配置的ID
                    default_profile = next((p for p in profiles if p.get("is_default", False)), profiles[0])
                    self.config[CURRENT_PROFILE_ID_KEY] = default_profile.get("id")

            # 使用简化的LLM配置系统，显示当前配置的API Key（默认配置=当前配置）
            if self.api_key_entry:
                current_profile = app_config.get_current_llm_profile(self.config)
                api_key_val = current_profile.get("api_key", "")
                self.api_key_entry.setText(api_key_val)

                # 根据当前配置中是否有API Key来设置复选框状态
                has_saved_api_key = bool(api_key_val)
                if hasattr(self, 'remember_api_key_checkbox'):
                    self.remember_api_key_checkbox.setChecked(has_saved_api_key)
            
            self.advanced_srt_settings = {
                'min_duration_target': self.config.get(USER_MIN_DURATION_TARGET_KEY, DEFAULT_MIN_DURATION_TARGET),
                'max_duration': self.config.get(USER_MAX_DURATION_KEY, DEFAULT_MAX_DURATION),
                'max_chars_per_line': self.config.get(USER_MAX_CHARS_PER_LINE_KEY, DEFAULT_MAX_CHARS_PER_LINE),
                'default_gap_ms': self.config.get(USER_DEFAULT_GAP_MS_KEY, DEFAULT_DEFAULT_GAP_MS),
            }
            self.free_transcription_settings = {
                'language': self.config.get(USER_FREE_TRANSCRIPTION_LANGUAGE_KEY, DEFAULT_FREE_TRANSCRIPTION_LANGUAGE),
                'num_speakers': self.config.get(USER_FREE_TRANSCRIPTION_NUM_SPEAKERS_KEY, DEFAULT_FREE_TRANSCRIPTION_NUM_SPEAKERS),
                'tag_audio_events': self.config.get(USER_FREE_TRANSCRIPTION_TAG_AUDIO_EVENTS_KEY, DEFAULT_FREE_TRANSCRIPTION_TAG_AUDIO_EVENTS),
            }
            # 初始化云端转录设置
            self.cloud_transcription_settings = {
                'provider': self.config.get('user_cloud_transcription_provider', DEFAULT_CLOUD_TRANSCRIPTION_PROVIDER),
                'elevenlabs_api_key': self.config.get('user_elevenlabs_api_key', DEFAULT_ELEVENLABS_API_KEY),
                'elevenlabs_api_remember_key': self.config.get('user_elevenlabs_api_remember_key', DEFAULT_ELEVENLABS_API_REMEMBER_KEY),
                'elevenlabs_api_language': self.config.get('user_elevenlabs_api_language', DEFAULT_ELEVENLABS_API_LANGUAGE),
                'elevenlabs_api_num_speakers': self.config.get('user_elevenlabs_api_num_speakers', DEFAULT_ELEVENLABS_API_NUM_SPEAKERS),
                'elevenlabs_api_enable_diarization': self.config.get('user_elevenlabs_api_enable_diarization', DEFAULT_ELEVENLABS_API_ENABLE_DIARIZATION),
                'elevenlabs_api_tag_audio_events': self.config.get('user_elevenlabs_api_tag_audio_events', DEFAULT_ELEVENLABS_API_TAG_AUDIO_EVENTS),
                'soniox_api_key': self.config.get('user_soniox_api_key', DEFAULT_SONIOX_API_KEY),
                'soniox_api_remember_key': self.config.get('user_soniox_api_remember_key', DEFAULT_SONIOX_API_REMEMBER_KEY),
                'soniox_language_hints': self.config.get('user_soniox_language_hints', DEFAULT_SONIOX_LANGUAGE_HINTS),
                'soniox_enable_speaker_diarization': self.config.get('user_soniox_enable_speaker_diarization', DEFAULT_SONIOX_ENABLE_SPEAKER_DIARIZATION),
                'soniox_enable_language_identification': self.config.get('user_soniox_enable_language_identification', DEFAULT_SONIOX_ENABLE_LANGUAGE_IDENTIFICATION),
                'soniox_context_terms': self.config.get('user_soniox_context_terms', DEFAULT_SONIOX_CONTEXT_TERMS),
                'soniox_context_text': self.config.get('user_soniox_context_text', DEFAULT_SONIOX_CONTEXT_TEXT),
                'soniox_context_general': self.config.get('user_soniox_context_general', DEFAULT_SONIOX_CONTEXT_GENERAL),
            }
            # 使用新的LLM配置系统获取当前配置
            current_profile = app_config.get_current_llm_profile(self.config)
            self.llm_advanced_settings = {
                USER_LLM_API_BASE_URL_KEY: current_profile.get("api_base_url", DEFAULT_LLM_API_BASE_URL),
                USER_LLM_MODEL_NAME_KEY: current_profile.get("model_name", DEFAULT_LLM_MODEL_NAME),
                USER_LLM_API_KEY_KEY: current_profile.get("api_key", DEFAULT_LLM_API_KEY),
                USER_LLM_REMEMBER_API_KEY_KEY: current_profile.get("remember_api_key", DEFAULT_LLM_REMEMBER_API_KEY),
                USER_LLM_TEMPERATURE_KEY: current_profile.get("temperature", DEFAULT_LLM_TEMPERATURE),
            }

            # 加载背景设置
            self.background_settings = {
                'enable_random': self.config.get(USER_ENABLE_RANDOM_BACKGROUND_KEY, DEFAULT_ENABLE_RANDOM_BACKGROUND),
                'custom_folder': self.config.get(USER_CUSTOM_BACKGROUND_FOLDER_KEY, DEFAULT_CUSTOM_BACKGROUND_FOLDER),
                'fixed_background_path': self.config.get(USER_FIXED_BACKGROUND_PATH_KEY, DEFAULT_FIXED_BACKGROUND_PATH),
                'background_source': self.config.get(USER_BACKGROUND_SOURCE_KEY, DEFAULT_BACKGROUND_SOURCE),
                'remembered_custom_folder': self.config.get(USER_REMEMBERED_CUSTOM_FOLDER_KEY, DEFAULT_REMEMBERED_CUSTOM_FOLDER),
                'remembered_custom_image': self.config.get(USER_REMEMBERED_CUSTOM_IMAGE_KEY, DEFAULT_REMEMBERED_CUSTOM_IMAGE),
            }

            # 总是以 local_json 模式启动，忽略上次保存的 input_mode
            self._current_input_mode = 'local_json'
            # Reset temporary audio file path
            self._temp_audio_file_for_free_transcription = None
            # 同步配置状态
            self.config['last_input_mode'] = 'local_json'
            self.config['last_free_transcription_audio_path'] = None
            
            if self.json_path_entry:
                # 直接加载JSON路径
                if os.path.isfile(self.config.get('last_json_path', '')):
                    self.json_path_entry.setText(self.config.get('last_json_path', ''))
            
            if self.json_format_combo:
                format_index = self.json_format_combo.findText(self.config.get('last_source_format', 'ElevenLabs(推荐)'))
                self.json_format_combo.setCurrentIndex(format_index if format_index != -1 else 0)

            # AI错词校对设置默认不保存，每次启动都重置为默认值
            if self.ai_correction_check:
                self.ai_correction_check.setChecked(app_config.DEFAULT_ENABLE_AI_CORRECTION)

            if self.output_path_entry:
                last_output = self.config.get('last_output_path', '')
                if os.path.isdir(last_output):
                    self.output_path_entry.setText(last_output)
                elif os.path.isdir(os.path.join(os.path.expanduser("~"),"Documents")):
                    self.output_path_entry.setText(os.path.join(os.path.expanduser("~"),"Documents"))
                else:
                    self.output_path_entry.setText(os.path.expanduser("~"))

            self._update_input_mode_ui() # 这将确保按钮基于强制的 'local_json' 模式正确更新

        except (json.JSONDecodeError, Exception) as e:
            # 使用改进的错误处理
            self.handle_error(e, "加载配置文件时发生错误", show_user_error=False)
            self.config = default_cfg_structure.copy()
            self.advanced_srt_settings = {
                'min_duration_target': DEFAULT_MIN_DURATION_TARGET, 'max_duration': DEFAULT_MAX_DURATION,
                'max_chars_per_line': DEFAULT_MAX_CHARS_PER_LINE, 'default_gap_ms': DEFAULT_DEFAULT_GAP_MS,
             }
            self.free_transcription_settings = {
                'language': DEFAULT_FREE_TRANSCRIPTION_LANGUAGE, 'num_speakers': DEFAULT_FREE_TRANSCRIPTION_NUM_SPEAKERS,
                'tag_audio_events': DEFAULT_FREE_TRANSCRIPTION_TAG_AUDIO_EVENTS,
             }
            self.cloud_transcription_settings = {
                'provider': DEFAULT_CLOUD_TRANSCRIPTION_PROVIDER,
                'elevenlabs_api_key': DEFAULT_ELEVENLABS_API_KEY,
                'elevenlabs_api_remember_key': DEFAULT_ELEVENLABS_API_REMEMBER_KEY,
                'elevenlabs_api_language': DEFAULT_ELEVENLABS_API_LANGUAGE,
                'elevenlabs_api_num_speakers': DEFAULT_ELEVENLABS_API_NUM_SPEAKERS,
                'elevenlabs_api_enable_diarization': DEFAULT_ELEVENLABS_API_ENABLE_DIARIZATION,
                'elevenlabs_api_tag_audio_events': DEFAULT_ELEVENLABS_API_TAG_AUDIO_EVENTS,
                'soniox_api_key': DEFAULT_SONIOX_API_KEY,
                'soniox_api_remember_key': DEFAULT_SONIOX_API_REMEMBER_KEY,
                'soniox_language_hints': DEFAULT_SONIOX_LANGUAGE_HINTS.copy(),
                'soniox_enable_speaker_diarization': DEFAULT_SONIOX_ENABLE_SPEAKER_DIARIZATION,
                'soniox_enable_language_identification': DEFAULT_SONIOX_ENABLE_LANGUAGE_IDENTIFICATION,
                'soniox_context_terms': DEFAULT_SONIOX_CONTEXT_TERMS,
                'soniox_context_text': DEFAULT_SONIOX_CONTEXT_TEXT,
                'soniox_context_general': DEFAULT_SONIOX_CONTEXT_GENERAL,
             }
            self.llm_advanced_settings = {
                USER_LLM_API_BASE_URL_KEY: DEFAULT_LLM_API_BASE_URL, USER_LLM_MODEL_NAME_KEY: DEFAULT_LLM_MODEL_NAME,
                USER_LLM_API_KEY_KEY: DEFAULT_LLM_API_KEY, USER_LLM_REMEMBER_API_KEY_KEY: DEFAULT_LLM_REMEMBER_API_KEY,
                USER_LLM_TEMPERATURE_KEY: DEFAULT_LLM_TEMPERATURE,
            }
            # 重置背景设置为默认值
            self.background_settings = {
                'enable_random': DEFAULT_ENABLE_RANDOM_BACKGROUND,
                'custom_folder': DEFAULT_CUSTOM_BACKGROUND_FOLDER,
                'fixed_background_path': DEFAULT_FIXED_BACKGROUND_PATH,
                'background_source': DEFAULT_BACKGROUND_SOURCE,
                'remembered_custom_folder': DEFAULT_REMEMBERED_CUSTOM_FOLDER,
                'remembered_custom_image': DEFAULT_REMEMBERED_CUSTOM_IMAGE,
            }
            # 确保在异常情况下也重置为 local_json 模式
            self._current_input_mode = 'local_json'
            self._temp_audio_file_for_free_transcription = None
            self._update_input_mode_ui()

    def save_config(self):
        if not (self.api_key_entry and \
                self.json_path_entry and self.output_path_entry and self.json_format_combo):
            self.log_message("警告: UI组件未完全初始化，无法保存配置。")
            return

        # 使用新的LLM配置系统，自动将API Key保存到当前配置中
        if self.api_key_entry:
            current_profile_id = self.config.get(CURRENT_PROFILE_ID_KEY, DEFAULT_CURRENT_PROFILE_ID)
            if current_profile_id:
                llm_profiles_config = self.config.get(LLM_PROFILES_KEY, {})
                profiles = llm_profiles_config.get("profiles", [])
                for profile in profiles:
                    if profile.get('id') == current_profile_id:
                        profile['api_key'] = self.api_key_entry.text().strip()
                        break

        if self.advanced_srt_settings:
            self.config[USER_MIN_DURATION_TARGET_KEY] = self.advanced_srt_settings.get('min_duration_target', DEFAULT_MIN_DURATION_TARGET)
            self.config[USER_MAX_DURATION_KEY] = self.advanced_srt_settings.get('max_duration', DEFAULT_MAX_DURATION)
            self.config[USER_MAX_CHARS_PER_LINE_KEY] = self.advanced_srt_settings.get('max_chars_per_line', DEFAULT_MAX_CHARS_PER_LINE)
            self.config[USER_DEFAULT_GAP_MS_KEY] = self.advanced_srt_settings.get('default_gap_ms', DEFAULT_DEFAULT_GAP_MS)
        
        if self.free_transcription_settings:
            self.config[USER_FREE_TRANSCRIPTION_LANGUAGE_KEY] = self.free_transcription_settings.get('language', DEFAULT_FREE_TRANSCRIPTION_LANGUAGE)
            self.config[USER_FREE_TRANSCRIPTION_NUM_SPEAKERS_KEY] = self.free_transcription_settings.get('num_speakers', DEFAULT_FREE_TRANSCRIPTION_NUM_SPEAKERS)
            self.config[USER_FREE_TRANSCRIPTION_TAG_AUDIO_EVENTS_KEY] = self.free_transcription_settings.get('tag_audio_events', DEFAULT_FREE_TRANSCRIPTION_TAG_AUDIO_EVENTS)

        # 保存背景配置
        if hasattr(self, 'background_settings'):
            self.config[USER_ENABLE_RANDOM_BACKGROUND_KEY] = self.background_settings.get('enable_random', DEFAULT_ENABLE_RANDOM_BACKGROUND)
            self.config[USER_CUSTOM_BACKGROUND_FOLDER_KEY] = self.background_settings.get('custom_folder', DEFAULT_CUSTOM_BACKGROUND_FOLDER)
            self.config[USER_FIXED_BACKGROUND_PATH_KEY] = self.background_settings.get('fixed_background_path', DEFAULT_FIXED_BACKGROUND_PATH)
            self.config[USER_BACKGROUND_SOURCE_KEY] = self.background_settings.get('background_source', DEFAULT_BACKGROUND_SOURCE)
            self.config[USER_REMEMBERED_CUSTOM_FOLDER_KEY] = self.background_settings.get('remembered_custom_folder', DEFAULT_REMEMBERED_CUSTOM_FOLDER)
            self.config[USER_REMEMBERED_CUSTOM_IMAGE_KEY] = self.background_settings.get('remembered_custom_image', DEFAULT_REMEMBERED_CUSTOM_IMAGE)

  
        # 保存云端转录配置
        if hasattr(self, 'cloud_transcription_settings') and self.cloud_transcription_settings:
            self.config[USER_CLOUD_TRANSCRIPTION_PROVIDER_KEY] = self.cloud_transcription_settings.get('provider', DEFAULT_CLOUD_TRANSCRIPTION_PROVIDER)

            # [修复] 只有在记住状态时才保存API Key，否则保存空字符串以清除已保存的Key
            el_remember = self.cloud_transcription_settings.get('elevenlabs_api_remember_key', False)
            self.config[USER_ELEVENLABS_API_REMEMBER_KEY_KEY] = el_remember
            if el_remember:
                self.config[USER_ELEVENLABS_API_KEY_KEY] = self.cloud_transcription_settings.get('elevenlabs_api_key', '')
            else:
                # 如果未勾选记住，确保不保存API Key
                self.config[USER_ELEVENLABS_API_KEY_KEY] = ''

            self.config[USER_ELEVENLABS_API_LANGUAGE_KEY] = self.cloud_transcription_settings.get('elevenlabs_api_language', 'auto')
            self.config[USER_ELEVENLABS_API_NUM_SPEAKERS_KEY] = self.cloud_transcription_settings.get('elevenlabs_api_num_speakers', 0)
            self.config[USER_ELEVENLABS_API_ENABLE_DIARIZATION_KEY] = self.cloud_transcription_settings.get('elevenlabs_api_enable_diarization', True)
            self.config[USER_ELEVENLABS_API_TAG_AUDIO_EVENTS_KEY] = self.cloud_transcription_settings.get('elevenlabs_api_tag_audio_events', True)

            # [修复] 只有在记住状态时才保存Soniox API Key
            sx_remember = self.cloud_transcription_settings.get('soniox_api_remember_key', False)
            self.config[USER_SONIOX_API_REMEMBER_KEY_KEY] = sx_remember
            if sx_remember:
                self.config[USER_SONIOX_API_KEY_KEY] = self.cloud_transcription_settings.get('soniox_api_key', '')
            else:
                # 如果未勾选记住，确保不保存API Key
                self.config[USER_SONIOX_API_KEY_KEY] = ''

            self.config[USER_SONIOX_LANGUAGE_HINTS_KEY] = self.cloud_transcription_settings.get('soniox_language_hints', ['ja', 'zh', 'en'])
            self.config[USER_SONIOX_ENABLE_SPEAKER_DIARIZATION_KEY] = self.cloud_transcription_settings.get('soniox_enable_speaker_diarization', True)
            self.config[USER_SONIOX_ENABLE_LANGUAGE_IDENTIFICATION_KEY] = self.cloud_transcription_settings.get('soniox_enable_language_identification', True)
            self.config[USER_SONIOX_CONTEXT_TERMS_KEY] = self.cloud_transcription_settings.get('soniox_context_terms', '')
            self.config[USER_SONIOX_CONTEXT_TEXT_KEY] = self.cloud_transcription_settings.get('soniox_context_text', '')
            self.config[USER_SONIOX_CONTEXT_GENERAL_KEY] = self.cloud_transcription_settings.get('soniox_context_general', '')
        
        self.config[USER_LLM_API_BASE_URL_KEY] = self.llm_advanced_settings.get(USER_LLM_API_BASE_URL_KEY, DEFAULT_LLM_API_BASE_URL)
        self.config[USER_LLM_MODEL_NAME_KEY] = self.llm_advanced_settings.get(USER_LLM_MODEL_NAME_KEY, DEFAULT_LLM_MODEL_NAME)
        self.config[USER_LLM_TEMPERATURE_KEY] = self.llm_advanced_settings.get(USER_LLM_TEMPERATURE_KEY, DEFAULT_LLM_TEMPERATURE)

        if self._current_input_mode == 'local_json':
            self.config['last_json_path'] = self.json_path_entry.text()
        elif self._temp_audio_file_for_free_transcription:
             self.config['last_free_transcription_audio_path'] = self._temp_audio_file_for_free_transcription
        
        self.config['last_output_path'] = self.output_path_entry.text()
        self.config['last_source_format'] = self.json_format_combo.currentText()
        self.config['last_input_mode'] = self._current_input_mode
        
        if USER_LLM_API_KEY_KEY in self.config and 'deepseek_api_key' in self.config:
            del self.config['deepseek_api_key']
        if USER_LLM_REMEMBER_API_KEY_KEY in self.config and 'remember_api_key' in self.config:
            del self.config['remember_api_key']

        try:
            # 优化：使用临时文件和原子写入，提高写入性能和安全性
            temp_config_file = CONFIG_FILE + '.tmp'
            with open(temp_config_file, 'w', encoding='utf-8', buffering=8192) as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False, separators=(',', ': '))

            # 原子性移动文件
            if os.path.exists(temp_config_file):
                import shutil
                shutil.move(temp_config_file, CONFIG_FILE)

        except Exception as e:
            # 使用改进的错误处理
            self.handle_error(e, "保存配置文件时发生错误", show_user_error=False)
            # 清理临时文件
            temp_file = CONFIG_FILE + '.tmp'
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

    def browse_json_file(self):
        if not self.json_path_entry: return
        if self._current_input_mode != "local_json":
            mode_text = "免费转录" if self._current_input_mode == "free_transcription" else "云端转录"
            self.log_message(f"提示：当前为'{mode_text}'模式，请通过对应对话框选择音频文件。")
            return

        # 优先使用配置中保存的路径
        config_json_path = self.config.get('last_json_path', '')
        if config_json_path and os.path.exists(os.path.dirname(config_json_path)):
            start_dir = os.path.dirname(config_json_path)
        elif self.json_path_entry.text() and os.path.exists(os.path.dirname(self.json_path_entry.text())):
            start_dir = os.path.dirname(self.json_path_entry.text())
        else:
            start_dir = os.path.expanduser("~")

        # 支持同时选择单个或多个JSON文件
        filepaths, _ = QFileDialog.getOpenFileNames(self, "选择 JSON 文件", start_dir, "JSON 文件 (*.json);;所有文件 (*.*)")

        if filepaths:
            # 文件类型验证：确保所有文件都是JSON文件
            valid_json_files = []
            for filepath in filepaths:
                if filepath.lower().endswith('.json'):
                    valid_json_files.append(filepath)
                else:
                    self.log_message(f"警告：文件 {os.path.basename(filepath)} 不是JSON文件，已跳过")

            if valid_json_files:
                if len(valid_json_files) == 1:
                    # 单个文件模式
                    self.json_path_entry.setText(valid_json_files[0])
                    self._batch_files = []  # 清空批量文件列表
                    self.log_message(f"已选择单个JSON文件: {os.path.basename(valid_json_files[0])}")
                else:
                    # 批量文件模式
                    self._batch_files = valid_json_files
                    self.json_path_entry.setText(f"已选择 {len(valid_json_files)} 个JSON文件")
                    self.log_message(f"已选择 {len(valid_json_files)} 个JSON文件进行批量处理")

                self._current_input_mode = "local_json"
                self._temp_audio_file_for_free_transcription = None
                self._update_input_mode_ui()
            else:
                self.log_message("错误：没有选择有效的JSON文件")
                QMessageBox.warning(self, "错误", "请选择有效的JSON文件")
        else:
            # 用户取消了选择
            self.json_path_entry.clear()
            self._batch_files = []  # 清空批量文件列表


    def select_output_dir(self):
        if not self.output_path_entry: return

        # 优先使用配置中保存的路径
        config_output_path = self.config.get('last_output_path', '')
        if config_output_path and os.path.isdir(config_output_path):
            start_dir = config_output_path
        elif self.output_path_entry.text() and os.path.isdir(self.output_path_entry.text()):
            start_dir = self.output_path_entry.text()
        else:
            start_dir = os.path.expanduser("~")

        dirpath = QFileDialog.getExistingDirectory(self, "选择导出目录", start_dir)
        if dirpath:
            self.output_path_entry.setText(dirpath)

    def open_settings_dialog(self):
        if not self.advanced_srt_settings:
             self.advanced_srt_settings = {
                'min_duration_target': self.config.get(USER_MIN_DURATION_TARGET_KEY, DEFAULT_MIN_DURATION_TARGET),
                'max_duration': self.config.get(USER_MAX_DURATION_KEY, DEFAULT_MAX_DURATION),
                'max_chars_per_line': self.config.get(USER_MAX_CHARS_PER_LINE_KEY, DEFAULT_MAX_CHARS_PER_LINE),
                'default_gap_ms': self.config.get(USER_DEFAULT_GAP_MS_KEY, DEFAULT_DEFAULT_GAP_MS),
             }

        # 只传递SRT设置
        dialog = SettingsDialog(self.advanced_srt_settings, self)
        dialog.settings_applied.connect(self.apply_srt_settings)
        dialog.exec()

    def apply_srt_settings(self, new_settings: dict):
        """应用SRT设置"""
        # 更新SRT设置
        self.advanced_srt_settings = {
            'min_duration_target': new_settings.get('min_duration_target', DEFAULT_MIN_DURATION_TARGET),
            'max_duration': new_settings.get('max_duration', DEFAULT_MAX_DURATION),
            'max_chars_per_line': new_settings.get('max_chars_per_line', DEFAULT_MAX_CHARS_PER_LINE),
            'default_gap_ms': new_settings.get('default_gap_ms', DEFAULT_DEFAULT_GAP_MS),
        }

        self.log_message("高级SRT参数已更新")
        self.save_config()

    def open_background_settings_dialog(self):
        """打开背景设置对话框"""
        # 确保配置是最新的
        self.config[USER_ENABLE_RANDOM_BACKGROUND_KEY] = self.background_settings.get('enable_random', DEFAULT_ENABLE_RANDOM_BACKGROUND)
        self.config[USER_CUSTOM_BACKGROUND_FOLDER_KEY] = self.background_settings.get('custom_folder', DEFAULT_CUSTOM_BACKGROUND_FOLDER)
        self.config[USER_FIXED_BACKGROUND_PATH_KEY] = self.background_settings.get('fixed_background_path', DEFAULT_FIXED_BACKGROUND_PATH)

        # 每次都创建新的对话框实例
        dialog = BackgroundSettingsDialog(self.config.copy(), self.background_manager, self)
        dialog.settings_applied.connect(self.apply_background_settings)

        # 显示对话框并等待结果
        result = dialog.exec()

        # 如果对话框被关闭（不管是否保存），都要同步配置
        if result == QDialog.DialogCode.Accepted:
            # 配置已经在apply_background_settings中处理
            pass

    def apply_background_settings(self, new_settings: dict):
        """应用背景设置"""
        old_enable_random = self.background_settings['enable_random']
        old_custom_folder = self.background_settings['custom_folder']
        old_fixed_background_path = self.background_settings.get('fixed_background_path', '')

        self.background_settings['enable_random'] = new_settings.get(USER_ENABLE_RANDOM_BACKGROUND_KEY, DEFAULT_ENABLE_RANDOM_BACKGROUND)
        self.background_settings['custom_folder'] = new_settings.get(USER_CUSTOM_BACKGROUND_FOLDER_KEY, DEFAULT_CUSTOM_BACKGROUND_FOLDER)
        self.background_settings['fixed_background_path'] = new_settings.get(USER_FIXED_BACKGROUND_PATH_KEY, DEFAULT_FIXED_BACKGROUND_PATH)
        self.background_settings['background_source'] = new_settings.get(USER_BACKGROUND_SOURCE_KEY, DEFAULT_BACKGROUND_SOURCE)
        self.background_settings['remembered_custom_folder'] = new_settings.get(USER_REMEMBERED_CUSTOM_FOLDER_KEY, DEFAULT_REMEMBERED_CUSTOM_FOLDER)
        self.background_settings['remembered_custom_image'] = new_settings.get(USER_REMEMBERED_CUSTOM_IMAGE_KEY, DEFAULT_REMEMBERED_CUSTOM_IMAGE)

        # 检查背景设置是否发生变化
        background_changed = (
            old_enable_random != self.background_settings['enable_random'] or
            old_custom_folder != self.background_settings['custom_folder'] or
            old_fixed_background_path != self.background_settings.get('fixed_background_path', '')
        )

        # 默认固定背景路径已经在对话框中正确设置，不需要额外处理
        # 对话框会自动将当前的last_background_path保存到fixed_background_path中

        # 记录日志
        if background_changed:
            self.log_message("背景设置已更新")

        # 如果背景设置发生变化，刷新背景
        if background_changed:
            self.refresh_background()

    def toggle_api_key_visibility(self):
        """切换API密钥的显示/隐藏状态"""
        if self.api_key_entry.echoMode() == QLineEdit.EchoMode.Password:
            # 当前是隐藏状态，切换到显示状态
            self.api_key_entry.setEchoMode(QLineEdit.EchoMode.Normal)

            # 设置睁眼图标
            if hasattr(self, 'eye_visible_path') and os.path.exists(self.eye_visible_path):
                eye_visible_pixmap = QPixmap(self.eye_visible_path)
                eye_visible_icon = QIcon(eye_visible_pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.api_key_visibility_button.setIcon(eye_visible_icon)

            self.api_key_visibility_button.setToolTip("隐藏 API Key")
        else:
            # 当前是显示状态，切换到隐藏状态
            self.api_key_entry.setEchoMode(QLineEdit.EchoMode.Password)

            # 设置闭眼图标
            if hasattr(self, 'eye_invisible_path') and os.path.exists(self.eye_invisible_path):
                eye_invisible_pixmap = QPixmap(self.eye_invisible_path)
                eye_invisible_icon = QIcon(eye_invisible_pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.api_key_visibility_button.setIcon(eye_invisible_icon)

            self.api_key_visibility_button.setToolTip("显示 API Key")

    def _on_remember_api_key_toggled(self, checked):
        """处理记住API Key复选框状态变化"""
        # 添加安全检查，确保属性已经初始化
        if not hasattr(self, 'config'):
            return

        # 更新记住状态到配置中
        self.config[USER_LLM_REMEMBER_API_KEY_KEY] = checked

        if checked:
            self.log_message("已启用 '记住 API Key'，程序关闭时将保存API Key")
        else:
            self.log_message("已禁用 '记住 API Key'，程序关闭时将清除保存的API Key")

    def _on_api_key_text_changed(self):
        """处理API Key输入框文本变化（简化设计：同步到当前配置）"""
        # 添加安全检查，确保属性已经初始化
        if not hasattr(self, 'config'):
            return

        current_ui_api_key = self.api_key_entry.text().strip()

        # 主界面的API Key同步到当前配置（默认配置=当前配置）
        if current_ui_api_key or current_ui_api_key == "":
            # 使用简化的同步方法
            self._sync_api_key_to_current_profile(current_ui_api_key)

    def _sync_api_key_between_windows(self, from_main_to_advanced=True):
        """双向同步API Key，支持从主窗口到配置或从配置到主窗口"""
        # 添加安全检查，确保属性已经初始化
        if not hasattr(self, 'config') or not hasattr(self, 'api_key_entry') or not hasattr(self, 'remember_api_key_checkbox'):
            return

        if from_main_to_advanced:
            # 从主窗口同步到配置
            current_ui_api_key = self.api_key_entry.text().strip()
            current_profile_id = self.config.get(app_config.CURRENT_PROFILE_ID_KEY)

            if current_profile_id:
                # 正确的配置结构：llm_profiles.profiles 是一个数组
                llm_profiles_config = self.config.get("llm_profiles", {})
                profiles_list = llm_profiles_config.get("profiles", [])

                # 在profiles数组中找到对应的profile
                for i, profile in enumerate(profiles_list):
                    if profile.get("id") == current_profile_id:
                        # 更新API Key
                        profiles_list[i]["api_key"] = current_ui_api_key
                        llm_profiles_config["profiles"] = profiles_list
                        self.config["llm_profiles"] = llm_profiles_config
                        break
        else:
            # 从配置同步到主窗口（原有的逻辑）
            current_profile = app_config.get_current_llm_profile(self.config)
            current_profile_api_key = current_profile.get("api_key", "")

            # 从高级管理同步到主窗口
            self.api_key_entry.setText(current_profile_api_key)

            # 更新复选框状态：如果当前配置有API Key，则勾选；否则不勾选
            has_saved_key = bool(current_profile_api_key)
            self.remember_api_key_checkbox.setChecked(has_saved_key)

            if has_saved_key:
                self.log_message("已从配置中同步API Key到主界面")
            else:
                self.log_message("当前配置无API Key，已清空主界面输入框")

    def test_llm_connection_from_main(self):
        """从主界面测试LLM连接"""
        # 获取当前的API配置
        api_key = self.api_key_entry.text().strip() if self.api_key_entry else ""
        if not api_key:
            QMessageBox.warning(self, "测试连接失败", "请先输入 API Key")
            return

        # 主界面应该测试当前活跃配置的连接
        current_profile = app_config.get_current_llm_profile(self.config)

        # 添加调试信息
        profile_name = current_profile.get("name", "未知配置")
        api_base_url = current_profile.get("api_base_url", DEFAULT_LLM_API_BASE_URL)
        available_models = current_profile.get("available_models", [])

        # 优先使用配置中的模型，如果为空则使用可用模型的第一个，最后才使用默认模型
        if current_profile.get("model_name"):
            model_name = current_profile.get("model_name")
        elif available_models:
            model_name = available_models[0]  # 使用可用模型的第一个
        else:
            model_name = DEFAULT_LLM_MODEL_NAME

        temperature = current_profile.get("temperature", DEFAULT_LLM_TEMPERATURE)

        # 尝试刷新模型列表（静默操作）
        try:
            # 调用模型刷新方法
            config_copy = self.config.copy()
            llm_advanced_settings_dialog = LlmAdvancedSettingsDialog(config_copy, self)
            refresh_success, models = llm_advanced_settings_dialog.refresh_available_models(api_key, api_base_url)
            llm_advanced_settings_dialog.close()

            # 如果刷新成功，更新本地配置
            if refresh_success:
                # 无需额外操作，配置已经在refresh_available_models中更新了
                pass
        except Exception:
            # 静默失败，不影响正常测试流程
            pass

        # 禁用测试按钮，显示测试中状态
        self.test_connection_button.setEnabled(False)
        self.test_connection_button.setText("⏳ 测试中...")

        # 创建并启动测试线程
        self.test_connection_thread = QThread()
        self.test_connection_worker = LlmTestWorker(api_key, api_base_url, model_name, temperature)
        self.test_connection_worker.moveToThread(self.test_connection_thread)

        # 连接信号
        self.test_connection_worker.finished.connect(self._on_test_connection_finished)
        self.test_connection_worker.log_message.connect(self.log_message)
        self.test_connection_thread.started.connect(self.test_connection_worker.run)

        # 启动测试
        self.test_connection_thread.start()

    def _on_test_connection_finished(self, success: bool, message: str):
        """测试连接完成的回调"""
        # 恢复按钮状态
        self.test_connection_button.setEnabled(True)
        self.test_connection_button.setText("🔗 测试当前配置连接")

        # 显示结果
        if success:
            QMessageBox.information(self, "连接测试成功", message)
            self.log_message(f"✅ LLM连接测试成功: {message}")
        else:
            QMessageBox.critical(self, "连接测试失败", f"连接失败：\n{message}")
            self.log_message(f"❌ LLM连接测试失败: {message}")

        # 清理线程
        if hasattr(self, 'test_connection_thread'):
            self.test_connection_thread.quit()
            self.test_connection_thread.wait()
            self.test_connection_thread = None

    def open_llm_advanced_settings_dialog(self):
        """打开LLM高级设置对话框"""
        try:
            # 在打开对话框之前，先同步主界面的API Key到当前活跃配置中
            # 主界面显示当前活跃配置的API Key，所以应该同步到当前活跃配置
            current_ui_api_key = self.api_key_entry.text().strip() if self.api_key_entry else ""
            if current_ui_api_key:
                # 主界面的API Key已经在_on_api_key_text_changed中同步到当前活跃配置
                # 这里不需要额外同步
                pass

            # 每次都创建新的对话框实例，这样会自动居中显示
            dialog = LlmAdvancedSettingsDialog(self.config.copy(), self)
            dialog.settings_applied.connect(self._on_llm_settings_saved)

            # 显示对话框并等待结果
            result = dialog.exec()

            # 如果对话框被关闭（不管是否保存），都要同步配置
            if result == QDialog.DialogCode.Accepted:
                # 用户点击了确认，配置已经通过settings_applied信号传递
                pass
            else:
                # 用户取消了操作，但仍然需要从对话框获取当前配置状态
                # 因为用户可能在界面上修改了API Key但没有保存
                if hasattr(dialog, 'current_config'):
                    # 强制同步当前配置状态
                    self._sync_api_key_between_windows(from_main_to_advanced=False)

        except Exception as e:
            print(f"[Error] 打开LLM设置对话框时出错: {e}")
            import traceback
            traceback.print_exc()

    def _load_custom_font_delayed(self):
        """延迟加载自定义字体，避免COM异常"""
        print("开始延迟加载自定义字体...")  # 只在终端显示
        try:
            custom_font_path = resource_path("fonts/猫啃忘形圆.ttf")
            if custom_font_path and os.path.exists(custom_font_path):
                # 使用字体文件路径创建字体ID
                font_id = QFontDatabase.addApplicationFont(custom_font_path)
                if font_id != -1:
                    font_families = QFontDatabase.applicationFontFamilies(font_id)
                    if font_families:
                        self.custom_font_family = font_families[0]
                        print(f"字体加载成功: {self.custom_font_family} (ID: {font_id})")  # 只在终端显示
                        # 检查可用的字重
                        available_weights = QFontDatabase.standardSizes()
                        print(f"字体可用标准大小: {available_weights}")  # 只在终端显示
                    else:
                        self.custom_font_family = "猫啃忘形圆"
                        print(f"字体族名获取失败，使用默认名称: {self.custom_font_family}")  # 只在终端显示
                else:
                    self.custom_font_family = "猫啃忘形圆"
                    print(f"警告: 字体文件加载失败: {custom_font_path}")  # 只在终端显示
            else:
                self.custom_font_family = "猫啃忘形圆"
                print(f"警告: 字体文件未找到: {custom_font_path}")  # 只在终端显示
        except Exception as e:
            self.custom_font_family = "Microsoft YaHei"  # 回退到系统字体
            print(f"字体加载异常，使用系统字体: {e}")  # 只在终端显示

        # 应用字体到整个应用
        QApplication.setFont(QFont(self.custom_font_family, self.base_font_size))
        # 刷新所有控件的字体
        # 延迟设置控件字体，确保字体已加载
        QTimer.singleShot(150, self._apply_fonts_to_controls)

    def _apply_fonts_to_controls(self):
        """应用字体到所有控件"""
        try:
            # 使用当前字体族名刷新所有控件
            self._update_control_heights()
        except Exception as e:
            self._early_log(f"应用字体到控件时出错: {e}")

    def _refresh_all_widget_fonts(self):
        """刷新所有控件的字体"""
        try:
            # 刷新主窗口及其子控件的字体
            self.setFont(QFont(self.custom_font_family, self.base_font_size))
            # 递归刷新所有子控件
            self._update_control_heights()
        except Exception as e:
            self._early_log(f"刷新字体时出错: {e}")

    def _on_llm_settings_saved(self, updated_config: dict):
        """当LLM高级设置对话框点击"确认"并保存后调用"""
        # 更新配置
        self.config.clear()
        self.config.update(updated_config)

        # 获取当前活跃配置并更新主界面（主界面应该始终显示当前活跃配置的API Key）
        current_profile = app_config.get_current_llm_profile(self.config)

        # 同步当前活跃配置的API Key到主界面
        if self.api_key_entry and current_profile:
            self.api_key_entry.setText(current_profile.get("api_key", ""))

            # 更新复选框状态：如果当前配置有API Key，则勾选；否则不勾选
            has_saved_key = bool(current_profile.get("api_key", ""))
            if hasattr(self, 'remember_api_key_checkbox'):
                self.remember_api_key_checkbox.setChecked(has_saved_key)

            if has_saved_key:
                self.log_message("已从当前配置同步API Key到主界面")
            else:
                self.log_message("当前配置无API Key，已清空主界面输入框")

        # 更新SRT处理器的配置（使用当前活跃配置）
        self.srt_processor.update_llm_config(
            api_key=current_profile.get("api_key", ""),
            base_url=current_profile.get("api_base_url", ""),
            model=current_profile.get("model_name", ""),
            temperature=current_profile.get("temperature", 0.2)
        )

        self.log_message("LLM配置已更新并保存。")

    def _get_default_llm_profile(self, config: dict) -> dict:
        """获取默认LLM配置"""
        profiles = config.get("llm_profiles", {}).get("profiles", [])

        # 查找标记为默认的配置
        for profile in profiles:
            if profile.get("is_default", False):
                return profile.copy()

        # 如果没有找到默认配置，返回空字典
        return {}

    def _sync_api_key_to_current_profile(self, api_key: str):
        """将API Key同步到当前配置（简化设计：当前配置=默认配置）"""
        if not hasattr(self, 'config'):
            return

        # 获取当前配置（在简化设计中，这就是默认配置）
        current_profile = app_config.get_current_llm_profile(self.config)
        if not current_profile:
            return

        current_profile_id = current_profile.get("id")
        if not current_profile_id:
            return

        # 正确的配置结构：llm_profiles.profiles 是一个数组
        llm_profiles_config = self.config.get("llm_profiles", {})
        profiles_list = llm_profiles_config.get("profiles", [])

        # 在profiles数组中找到当前配置并更新API Key
        for i, profile in enumerate(profiles_list):
            if profile.get("id") == current_profile_id:
                # 更新API Key（允许空字符串，用于清除API Key）
                profiles_list[i]["api_key"] = api_key
                llm_profiles_config["profiles"] = profiles_list
                self.config["llm_profiles"] = llm_profiles_config
                break

    def handle_free_transcription_button_click(self):
        """处理免费转录按钮点击事件，根据当前模式执行不同操作"""
        if self._free_transcription_button_is_in_cancel_mode:
            # 当前是取消模式，执行取消操作
            self._cancel_free_transcription_mode()
        else:
            # 当前是正常模式，打开免费转录对话框
            self._open_free_transcription_dialog()

    def _cancel_free_transcription_mode(self):
        """取消转录模式，恢复到本地JSON模式"""
        mode_text = "免费转录" if self._current_input_mode == "free_transcription" else "云端转录"
        self.log_message(f"用户取消{mode_text}模式，切换回本地JSON文件模式。")
        self._current_input_mode = "local_json"

        # 清除音频文件路径
        self._temp_audio_file_for_free_transcription = None
        self._batch_audio_files = []  # 清空批量音频文件

        # 尝试恢复上次的本地JSON路径
        if self.json_path_entry:
            last_json_path = self.config.get('last_json_path', '')
            self.json_path_entry.setText(last_json_path)
            if not last_json_path:
                self.json_path_entry.setPlaceholderText("选择包含ASR结果的 JSON 文件")

        # 更新UI状态
        self._update_input_mode_ui()

        # 保存配置
        self.save_config()

    def _open_free_transcription_dialog(self):
        """打开云端转录对话框"""
        dialog = CloudTranscriptionDialog(self)

        # 如果有预设的音频文件，设置到对话框中
        if self._temp_audio_file_for_free_transcription:
            dialog.selected_audio_file_path = self._temp_audio_file_for_free_transcription
            dialog.file_path_entry.setText(self._temp_audio_file_for_free_transcription)
            dialog.update_file_display()

        # 添加信号连接，确保用户的设置能够生效
        dialog.settings_confirmed.connect(self.apply_cloud_transcription_settings)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            pass
        else:
            self._cancel_free_transcription_mode()

    def apply_cloud_transcription_settings(self, new_settings: dict):
        """应用云端转录设置"""
        self._current_input_mode = "cloud_transcription"
        self._temp_audio_file_for_free_transcription = new_settings.get('audio_file_path')

        # 保存云端转录设置
        # [修复] 使用 update 而不是直接赋值，防止丢失其他服务商的 Key (例如 Soniox 的 Key)
        if not hasattr(self, 'cloud_transcription_settings') or not self.cloud_transcription_settings:
            self.cloud_transcription_settings = {}
        self.cloud_transcription_settings.update(new_settings)

        # 新增：处理批量音频文件
        self._batch_audio_files = new_settings.get('audio_files', [])

        if self.json_path_entry:
            if self._batch_audio_files:
                # 批量音频模式
                self.json_path_entry.setText(f"已选择 {len(self._batch_audio_files)} 个音频文件")
            elif self._temp_audio_file_for_free_transcription:
                # 单个音频模式
                provider_name = new_settings.get('provider', 'unknown').replace('_', ' ').title()
                self.json_path_entry.setText(f"{provider_name}: {os.path.basename(self._temp_audio_file_for_free_transcription)}")

        self._update_input_mode_ui()  # 这会更新按钮文本

        # 根据云端设置更新JSON格式下拉框
        if self.json_format_combo:
            source_format = self._get_source_format_from_cloud_settings()
            format_text_map = {
                'elevenlabs': 'ElevenLabs(推荐)',
                'elevenlabs_api': 'ElevenLabs(推荐)',
                'soniox': 'Soniox(推荐)',
                'whisper': 'Whisper(推荐)',
                'deepgram': 'Deepgram',
                'assemblyai': 'AssemblyAI'
            }
            format_text = format_text_map.get(source_format, 'ElevenLabs(推荐)')
            format_index = self.json_format_combo.findText(format_text)
            if format_index != -1:
                self.json_format_combo.setCurrentIndex(format_index)

        self.log_message(f"云端转录参数已更新: { {k:v for k,v in new_settings.items() if k not in ['audio_file_path', 'audio_files', 'api_key']} }")
        if self._batch_audio_files:
            self.log_message(f"  将批量处理 {len(self._batch_audio_files)} 个音频文件")
        elif self._temp_audio_file_for_free_transcription:
            provider_name = new_settings.get('provider', 'unknown').replace('_', ' ').title()
            self.log_message(f"  将使用 {provider_name} 处理音频文件: {self._temp_audio_file_for_free_transcription}")
        self.save_config()

    def apply_free_transcription_settings(self, new_settings: dict):
        self._current_input_mode = "free_transcription"
        self._temp_audio_file_for_free_transcription = new_settings.get('audio_file_path')

        # 新增：处理批量音频文件
        self._batch_audio_files = new_settings.get('audio_files', [])

        self.free_transcription_settings['language'] = new_settings.get('language')
        self.free_transcription_settings['num_speakers'] = new_settings.get('num_speakers')
        self.free_transcription_settings['tag_audio_events'] = new_settings.get('tag_audio_events')

        if self.json_path_entry:
            if self._batch_audio_files:
                # 批量音频模式
                self.json_path_entry.setText(f"已选择 {len(self._batch_audio_files)} 个音频文件")
            elif self._temp_audio_file_for_free_transcription:
                # 单个音频模式
                self.json_path_entry.setText(f"音频: {os.path.basename(self._temp_audio_file_for_free_transcription)}")

        self._update_input_mode_ui()  # 这会更新按钮文本
        self.log_message(f"免费转录参数已更新: { {k:v for k,v in new_settings.items() if k not in ['audio_file_path', 'audio_files']} }")
        if self._batch_audio_files:
            self.log_message(f"  将批量处理 {len(self._batch_audio_files)} 个音频文件")
        elif self._temp_audio_file_for_free_transcription:
            self.log_message(f"  将使用音频文件: {self._temp_audio_file_for_free_transcription}")
        self.save_config()


    
    
    def start_conversion(self):
        """
        开始转换 - 使用ConversionController管理业务逻辑
        """
        # 检查是否处于处理状态（作为停止按钮使用）
        if getattr(self, "is_processing", False):
            # 添加状态检查，确保控制器存在且可用
            if not self.conversion_controller:
                self.log_message("错误：正在处理状态但没有有效的控制器")
                return

            self.stop_conversion()
            return

        if not (self.api_key_entry and self.output_path_entry and \
                self.start_button and self.progress_bar and self.log_area and \
                self.json_format_combo and self.json_path_entry):
            QMessageBox.critical(self, "错误", "UI组件未完全初始化，无法开始转换。")
            return

        # 获取当前LLM配置（使用新的多配置系统）
        current_profile = app_config.get_current_llm_profile(self.config)

        current_ui_api_key = self.api_key_entry.text().strip()

        if current_ui_api_key:
            effective_api_key = current_ui_api_key
            # 同步API Key到当前配置
            self._sync_api_key_between_windows(from_main_to_advanced=True)

            # 无论是否勾选记住API Key，都要将API Key保存到当前配置中（以便转换使用）
            # 但是记住API Key控制的是程序重启后是否仍然保留
            self._sync_api_key_to_current_profile(effective_api_key)

            if self.remember_api_key_checkbox.isChecked():
                # 长期保存：保存到旧格式配置文件中
                self.config[USER_LLM_API_KEY_KEY] = effective_api_key
                self.config[USER_LLM_REMEMBER_API_KEY_KEY] = True
                self.log_message("API Key 已保存到配置文件（长期记住）")
            else:
                # 临时保存：只保存在当前配置中，不保存到旧格式配置
                if USER_LLM_API_KEY_KEY in self.config:
                    del self.config[USER_LLM_API_KEY_KEY]
                self.config[USER_LLM_REMEMBER_API_KEY_KEY] = False
                self.log_message("API Key 仅在本次会话中有效（不记住）")
        else:
            effective_api_key = current_profile.get("api_key", DEFAULT_LLM_API_KEY)
            # 如果主界面没有API Key，从配置同步到主界面
            if not effective_api_key:
                self.api_key_entry.setText("")
                self.remember_api_key_checkbox.setChecked(False)

        # 更新配置中的API Key信息
        if current_ui_api_key:
            current_profile["api_key"] = current_ui_api_key
            # 更新配置中的profile数据
            profiles = self.config.get(LLM_PROFILES_KEY, {}).get("profiles", [])
            current_profile_id = self.config.get(CURRENT_PROFILE_ID_KEY, DEFAULT_CURRENT_PROFILE_ID)

            for profile in profiles:
                if profile.get("id") == current_profile_id:
                    profile["api_key"] = current_ui_api_key
                    break

            self.config[LLM_PROFILES_KEY] = {"profiles": profiles}

        llm_base_url = current_profile.get("api_base_url", DEFAULT_LLM_API_BASE_URL)
        llm_model_name = current_profile.get("model_name", DEFAULT_LLM_MODEL_NAME)
        llm_temperature = current_profile.get("temperature", DEFAULT_LLM_TEMPERATURE)

        output_dir = self.output_path_entry.text().strip()

        if not effective_api_key:
            QMessageBox.warning(self, "缺少信息", "请在API设置或LLM高级设置中配置 API Key。"); return
        if not output_dir:
            QMessageBox.warning(self, "缺少信息", "请选择导出目录。"); return
        if not os.path.isdir(output_dir):
            QMessageBox.critical(self, "错误", f"导出目录无效: {output_dir}"); return

        # 配置SRT处理器
        self.srt_processor.configure_from_main_config(self.config)

        # [新增] 准备 SRT 参数字典
        # 确保这是一个字典，包含了当前 UI 上设置的值
        current_srt_params = self.advanced_srt_settings.copy()
        # 如果为空（未打开过设置），则从 config 中读取默认值构建
        if not current_srt_params:
             current_srt_params = {
                'min_duration_target': self.config.get(app_config.USER_MIN_DURATION_TARGET_KEY, app_config.DEFAULT_MIN_DURATION_TARGET),
                'max_duration': self.config.get(app_config.USER_MAX_DURATION_KEY, app_config.DEFAULT_MAX_DURATION),
                'max_chars_per_line': self.config.get(app_config.USER_MAX_CHARS_PER_LINE_KEY, app_config.DEFAULT_MAX_CHARS_PER_LINE),
                'default_gap_ms': self.config.get(app_config.USER_DEFAULT_GAP_MS_KEY, app_config.DEFAULT_DEFAULT_GAP_MS),
             }

        # 确保API Key已经正确同步到配置
        if current_ui_api_key:
            self.log_message(f"同步API Key到当前配置...")
            self._sync_api_key_to_current_profile(current_ui_api_key)
            # 立即保存配置以确保API Key被持久化
            self.save_config()
            self.log_message("配置已保存")

        self.progress_bar.setValue(0)
        self.log_message("--------------------")
        self.log_message("开始新的转换任务...")

        # 准备免费转录参数
        free_transcription_params = None
        if self._current_input_mode == "free_transcription":
            free_transcription_params = {
                **self.free_transcription_settings
            }

        # 使用ConversionController处理任务
        if self._current_input_mode in ["free_transcription", "cloud_transcription"]:
            # 检查是否有批量音频文件
            if self._batch_audio_files:
                # 批量音频处理模式
                self.log_message(f"检测到 {len(self._batch_audio_files)} 个音频文件，开始批量处理...")

                # 根据 self._current_input_mode 动态设置参数
                if self._current_input_mode == "free_transcription":
                    mode = "free_transcription"
                    source_format = "elevenlabs"  # 免费转录总是使用elevenlabs
                    cloud_params = None
                elif self._current_input_mode == "cloud_transcription":
                    mode = "cloud_transcription"
                    source_format = self._get_source_format_from_cloud_settings()
                    cloud_params = self.cloud_transcription_settings
                    free_transcription_params = None
                else:
                    # 默认回退到免费转录模式
                    mode = "free_transcription"
                    source_format = "elevenlabs"
                    cloud_params = None

                # 获取AI校正设置（批量云端转录模式也需要AI校正）
                enable_ai_correction = self.ai_correction_check.isChecked() if self.ai_correction_check else False

                self.conversion_controller.start_batch_task(
                    files=self._batch_audio_files,
                    output_dir=output_dir,
                    mode=mode,
                    free_params=free_transcription_params,
                    source_format=source_format,
                    cloud_params=cloud_params,
                    enable_ai_correction=enable_ai_correction,
                    srt_params=current_srt_params
                )
            else:
                # 单个音频文件模式
                if not self._temp_audio_file_for_free_transcription or \
                   not os.path.isfile(self._temp_audio_file_for_free_transcription):
                    mode_text = "云端转录" if self._current_input_mode == "cloud_transcription" else "免费转录"
                    QMessageBox.critical(self, "错误", f"请在'{mode_text}'中选择一个有效的音频文件。")
                    return

                if self._current_input_mode == "free_transcription":
                    free_transcription_params["audio_file_path"] = self._temp_audio_file_for_free_transcription
                    self.conversion_controller.start_single_task(
                        input_path="",  # 空字符串表示使用转录模式
                        output_dir=output_dir,
                        mode="free_transcription",
                        free_params=free_transcription_params,
                        source_format="elevenlabs",  # 免费转录总是使用elevenlabs
                        srt_params=current_srt_params
                    )
                else:  # cloud_transcription
                    # 获取AI校正设置（云端转录模式也需要AI校正）
                    enable_ai_correction = self.ai_correction_check.isChecked() if self.ai_correction_check else False

                    self.conversion_controller.start_single_task(
                        input_path="",  # 空字符串表示使用转录模式
                        output_dir=output_dir,
                        mode="cloud_transcription",
                        free_params=None,
                        source_format=self._get_source_format_from_cloud_settings(),
                        cloud_params=self.cloud_transcription_settings,
                        enable_ai_correction=enable_ai_correction,
                        srt_params=current_srt_params
                    )

        elif self._current_input_mode == "local_json":
            # 检查是否有批量文件
            if self._batch_files:
                # 批量处理模式
                # 获取AI纠错设置（批量JSON模式也需要AI校正）
                enable_ai_correction = self.ai_correction_check.isChecked() if self.ai_correction_check else False

                self.log_message(f"检测到 {len(self._batch_files)} 个文件，开始批量处理...")
                self.conversion_controller.start_batch_task(
                    files=self._batch_files,
                    output_dir=output_dir,
                    mode="local_json",
                    free_params=None,
                    source_format=self._get_source_format_from_combo(),
                    enable_ai_correction=enable_ai_correction,
                    srt_params=current_srt_params
                )
            else:
                # 单个文件模式
                json_path = self.json_path_entry.text().strip()
                if not json_path:
                    QMessageBox.warning(self, "缺少信息", "请选择 JSON 文件。"); return
                if not os.path.isfile(json_path):
                    QMessageBox.critical(self, "错误", f"JSON 文件不存在: {json_path}"); return

                # 获取AI纠错设置
                enable_ai_correction = self.ai_correction_check.isChecked() if self.ai_correction_check else False

                self.conversion_controller.start_single_task(
                    input_path=json_path,
                    output_dir=output_dir,
                    mode="local_json",
                    free_params=None,
                    source_format=self._get_source_format_from_combo(),
                    enable_ai_correction=enable_ai_correction,
                    srt_params=current_srt_params
                )
        else:
            QMessageBox.critical(self, "内部错误", "未知的输入模式。"); return

    def stop_conversion(self):
        """停止当前转换任务"""
        # 状态检查：确保确实有正在运行的任务
        if not getattr(self, "is_processing", False):
            self.log_message("没有正在运行的任务")
            return

        if not self.conversion_controller:
            self.log_message("错误：没有有效的转换控制器")
            # 强制重置状态
            self.is_processing = False
            if self.start_button:
                self.start_button.setEnabled(True)
                self.start_button.setText("开始转换")
                self.start_button.setStyleSheet(self._get_default_start_btn_style())
            return

        self.log_message("正在请求停止任务...")

        # 防止重复点击，更新按钮状态
        if self.start_button:
            self.start_button.setEnabled(False)
            self.start_button.setText("正在停止...")
            self.start_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(255, 158, 64, 180), stop:1 rgba(200, 100, 30, 200));
                    color: white;
                    border: 1px solid rgba(255, 158, 64, 150);
                    border-radius: 8px;
                    font-family: '楷体';
                    font-size: 15pt;
                    font-weight: bold;
                }
            """)

        try:
            self.conversion_controller.stop_task()
            self.log_message("已发送停止信号，等待任务完成...")

            # 【新增】立即重置进度条
            if self.progress_bar:
                self.progress_bar.setValue(0)

        except Exception as e:
            self.log_message(f"停止任务时发生错误: {e}")
            # 出错时重置状态
            self.is_processing = False
            if self.start_button:
                self.start_button.setEnabled(True)
                self.start_button.setText("开始转换")
                self.start_button.setStyleSheet(self._get_default_start_btn_style())

    def on_free_json_generated_by_worker(self, generated_json_path: str):
        self.log_message(f"Worker已生成JSON字幕: {generated_json_path}")
        pass

    def _on_task_started(self):
        """
        处理控制器任务开始信号
        """
        try:
            self.is_processing = True

            # 锁定其他控件
            self._set_all_controls_enabled(False)

            # 特殊处理 Start 按钮：保持启用，但变身
            if self.start_button:
                try:
                    self.start_button.setEnabled(True)
                    self.start_button.setText("停止任务 ⏹")
                    self.start_button.setStyleSheet("""
                QPushButton {
                    background-color: #d9534f;
                    color: white;
                    border-radius: 5px;
                    font-weight: bold;
                    font-family: 'Microsoft YaHei';
                    font-size: 14pt;
                }
                QPushButton:hover { background-color: #c9302c; }
            """)
                except Exception as e:
                    self.log_message(f"设置停止按钮状态时出错: {e}")

        except Exception as e:
            self.log_message(f"处理任务开始信号时发生错误: {e}")
            # 出错时强制重置状态
            try:
                self.is_processing = False
                if self.start_button:
                    self.start_button.setEnabled(True)
                    self.start_button.setText("开始转换")
                    self.start_button.setStyleSheet(self._get_default_start_btn_style())
                self._set_all_controls_enabled(True)
            except:
                pass

    def _set_all_controls_enabled(self, enabled: bool):
        """
        设置所有控件的可用状态

        Args:
            enabled: True为启用，False为禁用
        """
        # API Key相关控件
        if hasattr(self, 'api_key_entry') and self.api_key_entry:
            self.api_key_entry.setEnabled(enabled)
        if hasattr(self, 'api_key_visibility_button') and self.api_key_visibility_button:
            self.api_key_visibility_button.setEnabled(enabled)
        if hasattr(self, 'test_connection_button') and self.test_connection_button:
            self.test_connection_button.setEnabled(enabled)

        # 文件选择控件
        if hasattr(self, 'json_path_entry') and self.json_path_entry:
            self.json_path_entry.setEnabled(enabled)
        if hasattr(self, 'json_browse_button') and self.json_browse_button:
            self.json_browse_button.setEnabled(enabled)
        if hasattr(self, 'json_format_combo') and self.json_format_combo:
            self.json_format_combo.setEnabled(enabled)

        # AI校对复选框
        if hasattr(self, 'ai_correction_check') and self.ai_correction_check:
            self.ai_correction_check.setEnabled(enabled)

        # 输出路径控件
        if hasattr(self, 'output_path_entry') and self.output_path_entry:
            self.output_path_entry.setEnabled(enabled)
        if hasattr(self, 'output_browse_button') and self.output_browse_button:
            self.output_browse_button.setEnabled(enabled)

        # 其他按钮
        if hasattr(self, 'settings_button') and self.settings_button:
            self.settings_button.setEnabled(enabled)
        if hasattr(self, 'free_transcription_button') and self.free_transcription_button:
            # 如果不在取消模式，则禁用
            if not self._free_transcription_button_is_in_cancel_mode:
                self.free_transcription_button.setEnabled(enabled)
        if hasattr(self, 'llm_advanced_settings_button') and self.llm_advanced_settings_button:
            self.llm_advanced_settings_button.setEnabled(enabled)
        if hasattr(self, 'background_settings_button') and self.background_settings_button:
            self.background_settings_button.setEnabled(enabled)

        # 记住API Key复选框
        if hasattr(self, 'remember_api_key_checkbox') and self.remember_api_key_checkbox:
            self.remember_api_key_checkbox.setEnabled(enabled)

    def _on_task_finished(self, msg: str, success: bool):
        """
        处理控制器任务完成信号

        Args:
            msg: 完成消息
            success: 是否成功
        """
        try:
            # 确保状态重置
            if hasattr(self, 'is_processing'):
                self.is_processing = False

            # 恢复按钮
            if hasattr(self, 'start_button') and self.start_button:
                try:
                    self.start_button.setEnabled(True)
                    self.start_button.setText("开始转换")
                    # 恢复默认样式
                    self.start_button.setStyleSheet(self._get_default_start_btn_style())
                except Exception as e:
                    self.log_message(f"恢复按钮状态时出错: {e}")

            # 解锁其他控件
            try:
                self._set_all_controls_enabled(True)
            except Exception as e:
                self.log_message(f"解锁控件时出错: {e}")

            # 【新增】任务结束（无论成功失败），重置进度条
            if self.progress_bar:
                if success:
                    self.progress_bar.setValue(100)  # 确保显示满格
                    # 可选：延时 1 秒后归零，或者直接归零。这里按需求演示直接归零
                    # QTimer.singleShot(1000, lambda: self.progress_bar.setValue(0))
                    self.progress_bar.setValue(0)
                else:
                    self.progress_bar.setValue(0)

            # 重置免费转录/云端转录按钮状态
            if hasattr(self, 'free_transcription_button') and self.free_transcription_button:
                try:
                    self.free_transcription_button.setText("云端获取JSON")
                    self.free_transcription_button.setProperty("cancelMode", False)
                    self.free_transcription_button.style().unpolish(self.free_transcription_button)
                    self.free_transcription_button.style().polish(self.free_transcription_button)
                    self._free_transcription_button_is_in_cancel_mode = False
                except Exception as e:
                    self.log_message(f"重置转录按钮状态时出错: {e}")

            # 根据不同的完成状态显示不同的消息
            if success:
                if "任务已提前停止" in msg:
                    self.show_message_box(self, "任务已停止", msg, True)
                else:
                    self.show_message_box(self, "完成", msg, True)
            else:
                if "任务已提前停止" in msg:
                    self.show_message_box(self, "任务已停止", msg, True)
                else:
                    self.show_message_box(self, "错误", f"处理失败: {msg}", False)

        except Exception as e:
            self.log_message(f"处理任务完成信号时发生严重错误: {e}")
            # 出现严重错误时，强制重置UI状态
            try:
                if hasattr(self, 'is_processing'):
                    self.is_processing = False
                if hasattr(self, 'start_button') and self.start_button:
                    self.start_button.setEnabled(True)
                    self.start_button.setText("开始转换")
                    self.start_button.setStyleSheet(self._get_default_start_btn_style())
                if hasattr(self, '_set_all_controls_enabled'):
                    self._set_all_controls_enabled(True)
                self.log_message("已强制重置UI状态")
            except Exception as reset_error:
                self.log_message(f"强制重置UI状态也失败: {reset_error}")
                QMessageBox.critical(self, "严重错误", f"程序遇到严重错误，建议重启应用: {e}")

    def _get_default_start_btn_style(self):
        """获取开始按钮的默认样式"""
        return """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(64, 158, 255, 180), stop:1 rgba(30, 100, 200, 200));
                color: white;
                border: 1px solid rgba(64, 158, 255, 150);
                border-radius: 8px;
                font-family: '楷体';
                font-size: 15pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(64, 158, 255, 220);
            }
        """

    def _clear_worker_references(self):
        self.log_message("清理旧的worker和线程引用...")
        # 注意：这里保留是为了兼容性，但实际上worker管理已经移交给ConversionController
        if hasattr(self, 'conversion_controller'):
            self.conversion_controller.stop_task()

    def update_progress(self, value: int):
        if self.progress_bar:
            self.progress_bar.setFormat("%p%")
            self.progress_bar.setValue(value)

    def _on_upload_progress(self, bytes_read: int, total_bytes: int):
        """处理上传进度信号，在进度条上显示上传百分比。"""
        if self.progress_bar and total_bytes > 0:
            percent = int(bytes_read * 100 / total_bytes)
            self.progress_bar.setValue(percent)
            if percent >= 100:
                self.progress_bar.setFormat("等待转录结果...")
            else:
                self.progress_bar.setFormat(f"上传中... {percent}%")

    @staticmethod
    def show_message_box(parent_widget: Optional[QWidget], title: str, message: str, success: bool):
        if parent_widget and parent_widget.isVisible():
            QTimer.singleShot(0, lambda: (
                QMessageBox.information(parent_widget, title, message) if success
                else QMessageBox.critical(parent_widget, title, message)
            ))
        else:
            print(f"消息框 [{title} - {'成功' if success else '失败'}]: {message} (父控件不可用)")

    def on_conversion_finished(self, message: str, success: bool):
        """处理单文件转换完成"""
        if hasattr(self, 'start_button') and self.start_button:
             self.start_button.setEnabled(True)
             self.start_button.setText("开始转换")

        if self.progress_bar:
            if success:
                self.progress_bar.setValue(100)
            else:
                # 失败时强制归零进度条
                self.progress_bar.setValue(0)

        HealJimakuApp.show_message_box(self, "转换结果", message, success)

        self.log_message("任务结束，输入模式已重置为本地JSON文件模式。")
        self._current_input_mode = "local_json"

        last_local_json_path = self.config.get('last_json_path', '')
        if self.json_path_entry:
            self.json_path_entry.setText(last_local_json_path)
            if not last_local_json_path:
                 self.json_path_entry.setPlaceholderText("选择包含ASR结果的 JSON 文件")

        self._temp_audio_file_for_free_transcription = None
        self._update_input_mode_ui()  # 这会重置按钮文本
        self.save_config()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            title_bar_height = 80 
            is_on_title_bar_area = event.position().y() < title_bar_height
            widget_at_pos = self.childAt(event.position().toPoint())

            interactive_title_bar_buttons = {self.settings_button, self.llm_advanced_settings_button}
            if widget_at_pos in interactive_title_bar_buttons or \
               (hasattr(widget_at_pos, 'objectName') and widget_at_pos.objectName() in ["minButton", "closeButton"]):
                super().mousePressEvent(event)
                return

            is_interactive_control = False
            current_widget = widget_at_pos
            interactive_widgets_tuple = (QPushButton, QLineEdit, QCheckBox, QTextEdit, QProgressBar, QComboBox, QAbstractItemView, QDialog)
            
            active_popup = QApplication.activePopupWidget()
            if active_popup and active_popup.geometry().contains(event.globalPosition().toPoint()):
                super().mousePressEvent(event)
                return

            while current_widget is not None:
                if isinstance(current_widget, interactive_widgets_tuple) or \
                   (hasattr(current_widget, 'objectName') and current_widget.objectName().startswith('qt_scrollarea')):
                    is_interactive_control = True
                    break
                current_widget = current_widget.parentWidget()

            if is_on_title_bar_area and not is_interactive_control:
                self.drag_pos = event.globalPosition().toPoint()
                self.is_dragging = True
                event.accept()
            else:
                super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_dragging and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = event.globalPosition().toPoint()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_dragging and event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            event.accept()
        elif self._resize_mode != 0 and event.button() == Qt.MouseButton.LeftButton:
            # 结束大小调整
            self._resize_mode = 0
            self._resize_start_geometry = None

            # 恢复光标
            self.setCursor(Qt.CursorShape.ArrowCursor)
            try:
                from PyQt6.QtWidgets import QApplication
                QApplication.restoreOverrideCursor()
            except:
                pass

            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mousePressEvent(self, event):
        """处理鼠标按下事件，包括窗口大小调整"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 检查是否在边框区域（用于大小调整）
            resize_mode = self._get_resize_mode(event.position().toPoint())
            if resize_mode != 0:
                self._resize_mode = resize_mode
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geometry = self.geometry()
                event.accept()
                return

            # 原有的窗口拖动逻辑
            title_bar_height = 80
            is_on_title_bar_area = event.position().y() < title_bar_height
            widget_at_pos = self.childAt(event.position().toPoint())

            interactive_title_bar_buttons = {self.settings_button, self.llm_advanced_settings_button}
            if widget_at_pos in interactive_title_bar_buttons or \
               (hasattr(widget_at_pos, 'objectName') and widget_at_pos.objectName() in ["minButton", "closeButton"]):
                super().mousePressEvent(event)
                return

            is_interactive_control = False
            current_widget = widget_at_pos
            interactive_widgets_tuple = (QPushButton, QLineEdit, QCheckBox, QTextEdit, QProgressBar, QComboBox, QAbstractItemView, QDialog)

            active_popup = QApplication.activePopupWidget()
            if active_popup and active_popup.geometry().contains(event.globalPosition().toPoint()):
                super().mousePressEvent(event)
                return

            while current_widget is not None:
                if isinstance(current_widget, interactive_widgets_tuple) or \
                   (hasattr(current_widget, 'objectName') and current_widget.objectName().startswith('qt_scrollarea')):
                    is_interactive_control = True
                    break
                current_widget = current_widget.parentWidget()

            if is_on_title_bar_area and not is_interactive_control:
                self.drag_pos = event.globalPosition().toPoint()
                self.is_dragging = True
                event.accept()
            else:
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """处理鼠标移动事件，包括窗口大小调整"""
        if self.is_dragging and event.buttons() == Qt.MouseButton.LeftButton:
            # 窗口拖动
            self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = event.globalPosition().toPoint()
            event.accept()
        elif self._resize_mode != 0 and event.buttons() == Qt.MouseButton.LeftButton:
            # 窗口大小调整
            self._perform_resize(event.globalPosition().toPoint())
            event.accept()
        else:
            # 简化光标处理 - 无边框窗口光标显示有限制
            if not event.buttons() == Qt.MouseButton.LeftButton:
                resize_mode = self._get_resize_mode(event.position().toPoint())
                self._set_resize_cursor(resize_mode)
            super().mouseMoveEvent(event)

    def _get_resize_mode(self, pos):
        """根据鼠标位置获取调整大小模式"""
        x = pos.x()
        y = pos.y()
        width = self.width()
        height = self.height()

        mode = 0
        border = self._resize_border_width

        # 检查水平方向
        if x < border:
            mode |= 1  # 左边
        elif x > width - border:
            mode |= 2  # 右边

        # 检查垂直方向
        if y < border:
            mode |= 4  # 上边
        elif y > height - border:
            mode |= 8  # 下边

        return mode

    def _set_resize_cursor(self, resize_mode):
        """设置调整大小光标"""
        # Qt无边框窗口光标限制
        cursor_map = {
            0: Qt.CursorShape.ArrowCursor,      # 无调整
            1: Qt.CursorShape.SizeHorCursor,    # 左
            2: Qt.CursorShape.SizeHorCursor,    # 右
            4: Qt.CursorShape.SizeVerCursor,    # 上
            8: Qt.CursorShape.SizeVerCursor,    # 下
            5: Qt.CursorShape.SizeFDiagCursor,  # 左上
            6: Qt.CursorShape.SizeBDiagCursor,  # 右上
            9: Qt.CursorShape.SizeBDiagCursor,  # 左下
            10: Qt.CursorShape.SizeFDiagCursor, # 右下
        }

        cursor = cursor_map.get(resize_mode, Qt.CursorShape.ArrowCursor)

        # 尝试基本的光标设置（在无边框窗口中可能无效）
        try:
            self.setCursor(cursor)
        except Exception as e:
            # 接受Qt无边框窗口的光标限制
            pass

    def _perform_resize(self, global_pos):
        """执行窗口大小调整"""
        if not self._resize_start_geometry:
            return

        dx = global_pos.x() - self._resize_start_pos.x()
        dy = global_pos.y() - self._resize_start_pos.y()

        new_geometry = QRect(self._resize_start_geometry)

        # 根据调整模式更新几何形状
        if self._resize_mode & 1:  # 左边
            new_geometry.setLeft(new_geometry.left() + dx)
        if self._resize_mode & 2:  # 右边
            new_geometry.setRight(new_geometry.right() + dx)
        if self._resize_mode & 4:  # 上边
            new_geometry.setTop(new_geometry.top() + dy)
        if self._resize_mode & 8:  # 下边
            new_geometry.setBottom(new_geometry.bottom() + dy)

        # 确保窗口不小于最小尺寸
        min_width = self.minimumSize().width()
        min_height = self.minimumSize().height()

        if new_geometry.width() < min_width:
            if self._resize_mode & 1:
                new_geometry.setLeft(new_geometry.right() - min_width)
            else:
                new_geometry.setWidth(min_width)

        if new_geometry.height() < min_height:
            if self._resize_mode & 4:
                new_geometry.setTop(new_geometry.bottom() - min_height)
            else:
                new_geometry.setHeight(min_height)

        self.setGeometry(new_geometry)

    def _update_groupbox_style(self, groupbox, title_font_size):
        """动态更新QGroupBox的样式表以匹配字体大小"""
        if not groupbox or not hasattr(groupbox, 'objectName'):
            return

        obj_name = groupbox.objectName()
        if not obj_name:
            return

        # 根据对象名获取对应的标题颜色
        title_colors = {
            'apiGroup': '#B34A4A',
            'fileGroup': '#B34A4A',
            'exportGroup': '#B34A4A',
            'logGroup': '#B34A4A'
        }

        title_color = title_colors.get(obj_name, '#B34A4A')
        group_bg = "rgba(52, 129, 184, 30)"

        # 动态计算标题相关尺寸
        title_padding = max(2, int(title_font_size * 0.2))
        title_left_margin = max(10, int(title_font_size * 0.8))
        border_radius = max(6, int(title_font_size * 0.5))
        margin_top = max(8, int(title_font_size * 0.6))

        # 创建动态样式表
        style = f"""
            QGroupBox#{obj_name} {{
                font: bold {title_font_size}pt '{self.custom_font_family}';
                border: 1px solid rgba(135,206,235,80);
                border-radius:{border_radius}px;
                margin-top:{margin_top}px;
                background-color:{group_bg};
            }}
            QGroupBox#{obj_name}::title {{
                subcontrol-origin:margin;
                subcontrol-position:top left;
                left:{title_left_margin}px;
                padding:{title_padding}px 5px;
                color:{title_color};
                font:bold {title_font_size}pt '{self.custom_font_family}';
            }}
        """

        groupbox.setStyleSheet(style)

    def close_application(self):
        self.save_config()
        self.close()

    def closeEvent(self, event):
        """应用程序关闭事件处理"""
        self.log_message("正在关闭应用程序...")
        
        # 停止转换任务
        if self.conversion_controller:
            self.log_message("尝试停止正在进行的转换任务...")
            self.conversion_controller.stop_task()

        # 停止测试连接线程
        if hasattr(self, 'test_connection_thread') and self.test_connection_thread:
            if self.test_connection_thread.isRunning():
                self.test_connection_thread.quit()
                self.test_connection_thread.wait(1000)  # 等待最多1秒

        # 检查"记住API Key"复选框状态
        remember_api_key = False
        if hasattr(self, 'remember_api_key_checkbox'):
            remember_api_key = self.remember_api_key_checkbox.isChecked()

        if not remember_api_key:
            # 用户不记住API Key，需要清除配置中的API Key
            self._clear_api_key_from_current_profile()

            # 暂时清空输入框，避免save_config()重新保存
            temp_api_key = ""
            if hasattr(self, 'api_key_entry'):
                temp_api_key = self.api_key_entry.text()
                self.api_key_entry.setText("")

        # 保存配置
        self.save_config()

        # 如果用户不记住API Key，恢复输入框内容
        if not remember_api_key and hasattr(self, 'api_key_entry'):
            self.api_key_entry.setText(temp_api_key)

        # 接受关闭事件
        event.accept()
        
        # 不要在这里调用 quit()，让 main.py 中的 app.exec() 自然退出
        # QApplication.instance().quit()  # 移除这行，避免 COM 错误

    def _clear_api_key_from_current_profile(self):
        """清除当前默认配置中的API Key"""
        if not hasattr(self, 'config'):
            return

        current_profile_id = self.config.get(app_config.CURRENT_PROFILE_ID_KEY)
        if current_profile_id:
            # 正确的配置结构：llm_profiles.profiles 是一个数组
            llm_profiles_config = self.config.get("llm_profiles", {})
            profiles_list = llm_profiles_config.get("profiles", [])

            # 在profiles数组中找到对应的profile
            for i, profile in enumerate(profiles_list):
                if profile.get("id") == current_profile_id:
                    # 清除API Key
                    profiles_list[i]["api_key"] = ""
                    llm_profiles_config["profiles"] = profiles_list
                    self.config["llm_profiles"] = llm_profiles_config
                    self.log_message("程序关闭：已清除配置中的API Key（用户未选择记住）")
                    break

    # --- 拖拽处理相关方法 ---
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            # 检查文件类型是否合法
            urls = event.mimeData().urls()
            if self._validate_drag_files(urls):
                event.acceptProposedAction()
                self._show_drag_overlay()
            else:
                event.ignore()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """拖拽移动事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if self._validate_drag_files(urls):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """拖拽离开事件"""
        self._hide_drag_overlay()
        event.accept()

    def dropEvent(self, event):
        """拖拽释放事件"""
        self._hide_drag_overlay()

        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()

            # 验证文件类型
            if not self._validate_drag_files(urls):
                QMessageBox.warning(self, "拖拽错误", "拖拽的文件类型不合法或混合了不同类型文件。\n请只拖拽JSON文件或媒体文件。")
                event.ignore()
                return

            # 获取文件路径
            file_paths = [url.toLocalFile() for url in urls]

            # 处理拖拽的文件
            self._process_dropped_files(file_paths)
            event.acceptProposedAction()
        else:
            event.ignore()

    def _validate_drag_files(self, urls) -> bool:
        """验证拖拽的文件是否合法"""
        if not urls:
            return False

        # 支持的文件扩展名
        json_extensions = {'.json'}
        media_extensions = {
            '.mp3', '.wav', '.flac', '.m4a', '.ogg', '.opus', '.aac',
            '.webm', '.mp4', '.mov'
        }

        # 检查所有文件
        has_json = False
        has_media = False

        for url in urls:
            file_path = url.toLocalFile()
            if not os.path.isfile(file_path):
                return False  # 不是文件

            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext in json_extensions:
                has_json = True
            elif file_ext in media_extensions:
                has_media = True
            else:
                return False  # 不支持的扩展名

        # 不允许混合拖拽
        if has_json and has_media:
            return False

        return True

    def _process_dropped_files(self, file_paths):
        """处理拖拽的文件"""
        if not file_paths:
            return

        # 获取文件扩展名
        first_file_ext = os.path.splitext(file_paths[0])[1].lower()

        # JSON文件处理
        if first_file_ext == '.json':
            self._process_dropped_json_files(file_paths)
        # 媒体文件处理
        else:
            self._process_dropped_media_files(file_paths)

    def _process_dropped_json_files(self, json_files):
        """处理拖拽的JSON文件"""
        # 重置进度条
        if self.progress_bar:
            self.progress_bar.setValue(0)

        # 验证所有JSON文件
        valid_json_files = []
        for file_path in json_files:
            if file_path.lower().endswith('.json'):
                valid_json_files.append(file_path)
            else:
                self.log_message(f"警告：文件 {os.path.basename(file_path)} 不是JSON文件，已跳过")

        if not valid_json_files:
            QMessageBox.warning(self, "错误", "没有选择有效的JSON文件")
            return

        if len(valid_json_files) == 1:
            # 单个文件模式
            self.json_path_entry.setText(valid_json_files[0])
            self._batch_files = []  # 清空批量文件列表
            self.log_message(f"已选择单个JSON文件: {os.path.basename(valid_json_files[0])}")
        else:
            # 批量文件模式
            self._batch_files = valid_json_files
            self.json_path_entry.setText(f"已选择 {len(valid_json_files)} 个JSON文件")
            self.log_message(f"已选择 {len(valid_json_files)} 个JSON文件进行批量处理")

        self._current_input_mode = "local_json"
        self._temp_audio_file_for_free_transcription = None
        self._update_input_mode_ui()

    def _process_dropped_media_files(self, media_files):
        """处理拖拽的媒体文件"""
        # 验证所有媒体文件
        valid_media_files = []
        supported_extensions = {
            '.mp3', '.wav', '.flac', '.m4a', '.ogg', '.opus', '.aac',
            '.webm', '.mp4', '.mov'
        }

        for file_path in media_files:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext in supported_extensions:
                valid_media_files.append(file_path)
            else:
                self.log_message(f"警告：文件 {os.path.basename(file_path)} 不是支持的媒体文件，已跳过")

        if not valid_media_files:
            QMessageBox.warning(self, "错误", "没有选择有效的媒体文件")
            return

        # 打开JSON输出设置对话框
        self._open_media_drop_settings_dialog(valid_media_files)

    def _open_media_drop_settings_dialog(self, media_files):
        """打开媒体文件拖拽时的云端转录设置对话框"""
        # 创建并显示云端转录对话框
        dialog = CloudTranscriptionDialog(self)

        # 预设文件信息
        if len(media_files) == 1:
            dialog.selected_audio_file_path = media_files[0]
            dialog.file_path_entry.setText(media_files[0])
            dialog.update_file_display()  # 更新文件显示
        else:
            dialog.selected_audio_files = media_files
            dialog.selected_audio_file_path = ""  # 清空单个文件路径
            dialog.file_path_entry.setText(f"已选择 {len(media_files)} 个音频文件")
            dialog.update_file_display()  # 更新文件显示

        # 添加信号连接，确保用户的设置能够生效
        dialog.settings_confirmed.connect(self.apply_cloud_transcription_settings)

        # === 修改开始：强制置顶主窗口 ===
        # 在显示对话框之前，强制激活主窗口，确保它浮在文件资源管理器之上
        self.activateWindow()
        self.raise_()
        # 可选：处理一下积压的事件，确保窗口重绘完成
        QApplication.processEvents()
        # === 修改结束 ===

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 对话框已确认，云端转录逻辑会在对话框内部处理
            # 不需要额外处理，因为新对话框会自动处理文件上传和转录流程
            pass
        else:
            # 用户取消设置，恢复到本地JSON模式
            self._current_input_mode = "local_json"
            if self.json_path_entry:
                last_json_path = self.config.get('last_json_path', '')
                self.json_path_entry.setText(last_json_path)
                if not last_json_path:
                    self.json_path_entry.setPlaceholderText("选择包含ASR结果的 JSON 文件")
            self._update_input_mode_ui()

    def _apply_media_drop_settings(self, new_settings: dict, media_files):
        """应用媒体文件拖拽的设置"""
        if len(media_files) == 1:
            # 单个文件模式
            self._current_input_mode = "free_transcription"
            self._temp_audio_file_for_free_transcription = media_files[0]
            self._batch_audio_files = []  # 清空批量音频文件

            if self.json_path_entry:
                self.json_path_entry.setText(f"音频: {os.path.basename(media_files[0])}")

            self.log_message(f"已选择单个音频文件: {os.path.basename(media_files[0])}")
        else:
            # 批量文件模式
            self._current_input_mode = "free_transcription"
            self._batch_audio_files = media_files
            self._temp_audio_file_for_free_transcription = None

            if self.json_path_entry:
                self.json_path_entry.setText(f"已选择 {len(media_files)} 个音频文件")

            self.log_message(f"已选择 {len(media_files)} 个音频文件进行批量处理")

        # 更新免费转录设置
        self.free_transcription_settings.update({
            'language': new_settings.get('language', 'auto'),
            'num_speakers': new_settings.get('num_speakers', 0),
            'tag_audio_events': new_settings.get('tag_audio_events', False)
        })

        self._update_input_mode_ui()

    def _show_drag_overlay(self):
        """显示拖拽覆盖层"""
        if self.is_drag_overlay_visible:
            return

        self.is_drag_overlay_visible = True

        # 创建覆盖层
        self.drag_overlay_widget = QWidget(self)
        self.drag_overlay_widget.setObjectName("dragOverlay")
        self.drag_overlay_widget.setGeometry(self.rect())

        # 设置样式
        self.drag_overlay_widget.setStyleSheet("""
            QWidget#dragOverlay {
                background-color: rgba(0, 0, 0, 150);
            }
        """)

        # 创建拖拽区域
        drag_area = QWidget(self.drag_overlay_widget)
        drag_area.setObjectName("dragArea")

        # 计算位置和大小（占据窗口70%）
        window_width = self.width()
        window_height = self.height()
        area_width = int(window_width * 0.7)
        area_height = int(window_height * 0.7)
        area_x = (window_width - area_width) // 2
        area_y = (window_height - area_height) // 2

        drag_area.setGeometry(area_x, area_y, area_width, area_height)

        # 设置拖拽区域样式
        drag_area.setStyleSheet("""
            QWidget#dragArea {
                background-color: rgba(255, 255, 255, 180);
                border: 3px dashed rgba(100, 149, 237, 200);
                border-radius: 15px;
            }
        """)

        # 添加文字标签
        label = QLabel("请拖拽到此处", drag_area)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                font-family: '{self.custom_font_family}';
                font-size: 24pt;
                font-weight: bold;
                background-color: transparent;
            }
        """)
        label.setGeometry(0, 0, area_width, area_height)

        self.drag_overlay_widget.show()
        self.drag_overlay_widget.raise_()

    def _hide_drag_overlay(self):
        """隐藏拖拽覆盖层"""
        if self.drag_overlay_widget:
            self.drag_overlay_widget.hide()
            self.drag_overlay_widget.deleteLater()
            self.drag_overlay_widget = None

        self.is_drag_overlay_visible = False

    def _auto_refresh_all_models_on_startup(self):
        """在程序启动时自动刷新所有API配置的模型列表"""
        try:
            # 获取所有API配置（正确的配置结构）
            llm_profiles_config = self.config.get("llm_profiles", {})
            profiles_list = llm_profiles_config.get("profiles", [])

            if not profiles_list or not isinstance(profiles_list, list):
                return

            # 遍历所有配置文件
            for i, profile in enumerate(profiles_list):
                try:
                    # 检查配置是否有效（有API地址和密钥）
                    api_url = profile.get("api_base_url", "")
                    api_key = profile.get("api_key", "")
                    profile_name = profile.get("name", f"配置{i}")

                    # 静默跳过没有API地址或密钥的配置，不显示警告
                    if not api_url or not api_key:
                        continue

                    # 获取模型列表（静默操作）
                    try:
                        # 创建配置副本用于刷新
                        temp_config = self.config.copy()
                        temp_config[app_config.CURRENT_PROFILE_ID_KEY] = profile.get("id")
                        llm_advanced_settings_dialog = LlmAdvancedSettingsDialog(temp_config, self)
                        refresh_success, models = llm_advanced_settings_dialog.refresh_available_models(api_key, api_url)

                        # 更新可用模型列表
                        if refresh_success and models:
                            profiles_list[i]["available_models"] = models

                        llm_advanced_settings_dialog.close()

                    except Exception as e:
                        # 静默失败，不显示错误消息
                        pass

                except Exception as e:
                    # 静默失败，不显示错误消息
                    pass

            # 保存更新的配置（静默更新，不通知用户）
            if profiles_list:
                llm_profiles_config["profiles"] = profiles_list
                self.config["llm_profiles"] = llm_profiles_config
                # 保存到配置文件
                app_config.save_config(self.config)

        except Exception:
            # 静默失败，不影响程序启动
            pass