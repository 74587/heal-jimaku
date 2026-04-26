import os
import json
import uuid
from typing import Optional, Dict, Any, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QSlider, QMessageBox, QSpacerItem, QSizePolicy, QApplication,
    QWidget, QComboBox, QListWidget, QListWidgetItem, QGroupBox, QFormLayout,
    QSplitter, QTextEdit, QFrame, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, QObject, QPoint, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QFont, QColor

import config
from ui.custom_widgets import CustomLabel, CustomLabel_title
from utils.file_utils import resource_path

ICON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "info_icon.png"))

class LlmTestWorker(QObject):
    """LLM连接测试工作线程，负责异步测试API连接状态"""
    finished = pyqtSignal(bool, str)
    log_message = pyqtSignal(str)  # 日志输出信号

    def __init__(self, api_key: str, base_url: str, model_name: str, temperature: float, api_format: str = None):
        super().__init__()
        self._api_key = api_key
        self._base_url = base_url
        self._model_name = model_name
        self._temperature = temperature
        self._api_format = api_format

    def run(self):
        """运行LLM连接测试"""
        try:
            from core import llm_api
            # 调用LLM API测试连接
            success, message = llm_api.test_llm_connection(
                api_key=self._api_key,
                custom_api_base_url_str=self._base_url,
                custom_model_name=self._model_name,
                custom_temperature=self._temperature,
                signals_forwarder=self,  # 传递自身作为信号转发器
                api_format=self._api_format  # 传递API格式参数
            )
            self.finished.emit(success, message)
        except Exception as e:
            self.finished.emit(False, f"测试连接时发生内部错误: {e}")


class ModelFetchWorker(QObject):
    """获取模型列表的工作线程"""
    finished = pyqtSignal(list, str)
    log_message = pyqtSignal(str)

    def __init__(self, api_base_url: str, api_key: str, provider: str):
        super().__init__()
        self._api_base_url = api_base_url
        self._api_key = api_key
        self._provider = provider

    def run(self):
        """获取模型列表"""
        try:
            models, message = self._fetch_models()
            self.finished.emit(models, message)
        except Exception as e:
            self.finished.emit([], f"获取模型列表失败: {e}")

    def _fetch_models(self):
        """获取模型列表 - 根据 API 格式而不是域名判断"""
        # [FIX] 将 UI 格式文本转换为内部格式常量
        api_format_map = {
            "OpenAI兼容": config.API_FORMAT_OPENAI,
            "Claude格式": config.API_FORMAT_CLAUDE,
            "Gemini格式": config.API_FORMAT_GEMINI,
            "自动检测": config.API_FORMAT_AUTO
        }
        api_format = api_format_map.get(self._provider, config.API_FORMAT_AUTO)
        
        # 检查是否为官方API（用于决定是否尝试实时获取）
        official_domains = [
            "api.openai.com",
            "api.anthropic.com",
            "generativelanguage.googleapis.com",
            "api.deepseek.com"
        ]
        is_official_api = any(domain in self._api_base_url for domain in official_domains)

        # 根据 API 格式决定如何获取模型
        if api_format == config.API_FORMAT_CLAUDE or "api.anthropic.com" in self._api_base_url:
            # Claude: 使用静态列表（Claude API 不提供模型列表接口）
            models = [
                "claude-opus-4-1-20250805",
                "claude-sonnet-4-5-20250929",
                "claude-haiku-4-5-20251001",
                "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307",
                "claude-2.1", "claude-2.0", "claude-instant-1.2"
            ]
            return models, "使用Claude已知模型列表"
            
        elif api_format == config.API_FORMAT_GEMINI or "generativelanguage.googleapis.com" in self._api_base_url:
            # Gemini: 尝试实时获取
            try:
                import requests
                url = f"{self._api_base_url.rstrip('/')}/v1beta/models?key={self._api_key}"
                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    if "models" in data and isinstance(data["models"], list):
                        models = [model["name"].split("/")[-1] for model in data["models"] if "name" in model]
                        return models, f"成功获取Gemini实时模型列表，共{len(models)}个模型"
            except Exception:
                pass
            # 失败时返回静态列表
            models = ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro", "gemini-pro-vision"]
            return models, "API调用失败，使用Gemini默认模型列表"
            
        else:
            # OpenAI 兼容格式（包括 AUTO 模式）：尝试调用 /v1/models
            try:
                import requests
                url = f"{self._api_base_url.rstrip('/')}/v1/models"
                headers = {"Authorization": f"Bearer {self._api_key}"}
                response = requests.get(url, headers=headers, timeout=15)

                if response.status_code == 200:
                    data = response.json()
                    if "data" in data and isinstance(data["data"], list):
                        models = [model["id"] for model in data["data"] if isinstance(model, dict) and "id" in model]
                        return models, f"成功获取模型列表，共{len(models)}个模型"
            except Exception:
                pass

            # 失败时根据域名返回对应的静态列表
            if "api.openai.com" in self._api_base_url:
                models = ["gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
                return models, "API调用失败，使用OpenAI默认模型列表"
            elif "api.deepseek.com" in self._api_base_url:
                models = ["deepseek-v4-flash", "deepseek-v4-pro"]
                return models, "API调用失败，使用DeepSeek默认模型列表"
            else:
                # 通用模型列表（适用于第三方代理）
                models = [
                    "gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-4o-mini",
                    "gpt-3.5-turbo", "gpt-3.5-turbo-16k",
                    "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022",
                    "gemini-1.5-pro", "gemini-1.5-flash",
                    "deepseek-v4-flash", "deepseek-v4-pro"
                ]
                return models, "API调用失败，使用通用模型列表"


class LlmAdvancedSettingsDialog(QDialog):
    """LLM高级设置和模型管理对话框"""

    settings_applied = pyqtSignal(dict)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.parent_window = parent  # 保存主界面引用
        self.profiles = []
        self.current_profile_id = None
        self.test_worker = None
        self.test_thread = None
        self.fetch_worker = None
        self.fetch_thread = None

        # UI组件
        self.profile_list: Optional[QListWidget] = None
        self.profile_name_edit: Optional[QLineEdit] = None
        self.provider_combo: Optional[QComboBox] = None
        self.api_url_edit: Optional[QLineEdit] = None
        self.model_name_combo: Optional[QComboBox] = None
        self.api_key_edit: Optional[QLineEdit] = None
        self.temperature_slider: Optional[QSlider] = None
        self.temperature_value_label: Optional[QLabel] = None
        self.thinking_slider: Optional[QSlider] = None
        self.thinking_value_label: Optional[QLabel] = None

        # 描边颜色设置 (与主窗口一致)
        self.target_main_color = QColor(92, 138, 111)
        self.target_stroke_color = QColor(242, 234, 218)

        self.setWindowTitle("LLM高级设置")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 根据屏幕大小动态调整对话框尺寸
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            screen_height = screen_geometry.height()
            
            # 如果屏幕高度小于1000px，使用较小尺寸并启用滚动
            if screen_height < 1000:
                dialog_width = 820  # 从750增加到820，给滚动条留更多空间
                dialog_height = min(680, int(screen_height * 0.88))  # 最多占屏幕88%
                self.use_scroll = True
            else:
                dialog_width = 900  # 从850增加到900
                dialog_height = 780
                self.use_scroll = False
        else:
            dialog_width = 900
            dialog_height = 780
            self.use_scroll = False
        
        self.setFixedSize(dialog_width, dialog_height)

        # 创建半透明容器
        self.container = QWidget(self)
        self.container.setObjectName("llmSettingsDialogContainer")
        self.container.setGeometry(0, 0, dialog_width, dialog_height)

        # 主布局
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0,0,0,0)
        dialog_layout.addWidget(self.container)

        self.inner_content_layout = QVBoxLayout(self.container)
        self.inner_content_layout.setContentsMargins(25, 20, 25, 20)
        self.inner_content_layout.setSpacing(18)

        # 初始化UI并应用样式
        self._init_ui()
        self._apply_styles()
        self._connect_signals()
        self._load_profiles_to_ui()

        # 将对话框居中到父窗口
        if self.parent_window:
            parent_geometry = self.parent_window.geometry()
            # 使用动态计算的尺寸
            # 计算居中位置
            center_x = parent_geometry.x() + (parent_geometry.width() - dialog_width) // 2
            center_y = parent_geometry.y() + (parent_geometry.height() - dialog_height) // 2

            self.move(center_x, center_y)

    def _init_ui(self):
        """初始化对话框UI组件"""
        # 创建标题栏
        title_bar_layout = QHBoxLayout()
        title_label = CustomLabel_title("LLM高级管理")
        title_label.setCustomColors(main_color="#4A7CB3", stroke_color=self.target_stroke_color)  # 改为蓝色
        # 不再重复设置字体，让CustomLabel_title类自己处理楷体字体
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 使用自定义圆形关闭按钮图片
        close_button = QPushButton()
        close_button.setFixedSize(30, 30)
        close_button.setObjectName("dialogCloseButton")
        close_button.setToolTip("关闭")
        close_button.clicked.connect(self.reject)

        # 设置圆形关闭按钮的样式和图标
        close_path = resource_path('dialog_close_normal.png')
        close_hover_path = resource_path('dialog_close_hover.png')
        if close_path and os.path.exists(close_path):
            close_button.setIcon(QIcon(close_path))
            close_button.setIconSize(QSize(30, 30))
        else:
            close_button.setText("×")

        title_bar_layout.addStretch()
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(close_button)
        self.inner_content_layout.addLayout(title_bar_layout)

        # 创建主分割器 - 设置1:3比例
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：模型列表（占1/4）
        left_panel = self._create_profile_list_panel()
        left_panel.setMinimumWidth(220)
        left_panel.setMaximumWidth(280)
        main_splitter.addWidget(left_panel)

        # 右侧：配置编辑（占3/4）
        right_panel = self._create_config_panel()
        right_panel.setMinimumWidth(500)  # 原始右侧面板最小宽度
        main_splitter.addWidget(right_panel)

        # 设置分割器比例为1:3
        main_splitter.setSizes([220, 660])
        main_splitter.setStretchFactor(0, 1)  # 左侧不拉伸
        main_splitter.setStretchFactor(1, 3)  # 右侧拉伸3倍

        # 如果需要滚动支持，用QScrollArea包装main_splitter
        if self.use_scroll:
            from PyQt6.QtWidgets import QScrollArea
            scroll_area = QScrollArea()
            
            # 创建一个容器来包装main_splitter，并添加右侧内边距
            scroll_content = QWidget()
            scroll_content_layout = QVBoxLayout(scroll_content)
            scroll_content_layout.setContentsMargins(0, 0, 15, 0)  # 右侧留15px给滚动条
            scroll_content_layout.addWidget(main_splitter)
            
            scroll_area.setWidget(scroll_content)
            scroll_area.setWidgetResizable(True)
            scroll_area.setStyleSheet("""
                QScrollArea {
                    background: transparent;
                    border: none;
                }
                QScrollArea > QWidget > QWidget {
                    background: transparent;
                }
            """)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.inner_content_layout.addWidget(scroll_area)
        else:
            self.inner_content_layout.addWidget(main_splitter)

    def _create_profile_list_panel(self) -> QWidget:
        """创建左侧模型列表面板 - 包含模型列表和2x2快速模板按钮"""
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setSpacing(12)

        # 列表标题 - 使用与主窗口日志标题相同的颜色样式
        list_title = CustomLabel("模型配置列表")
        list_title.setCustomColors(main_color="#B34A4A", stroke_color=self.target_stroke_color)
        title_font = QFont('楷体', 15, QFont.Weight.Bold)
        list_title.setFont(title_font)
        panel_layout.addWidget(list_title)

        # 模型列表 - 减少高度为快速模板腾出空间
        self.profile_list = QListWidget()
        self.profile_list.setObjectName("profileList")
        self.profile_list.setMinimumHeight(180)  # 进一步减少高度
        self.profile_list.setMaximumHeight(180)  # 设置最大高度限制
        panel_layout.addWidget(self.profile_list)

        # 添加间距
        panel_layout.addSpacing(12)  # 减少间距

        # 快速模板组
        template_group = QGroupBox("快速模板")
        template_layout = QVBoxLayout(template_group)
        template_layout.setContentsMargins(10, 10, 10, 10)  # 正常边距

        # 4行垂直布局的模板按钮
        template_grid = QVBoxLayout()
        template_grid.setSpacing(8)  # 适中的按钮间距

        # OpenAI 按钮
        openai_template_btn = QPushButton("OpenAI")
        openai_template_btn.setObjectName("templateButton")
        openai_template_btn.setFixedHeight(36)  # 适中高度，宽度自适应
        openai_template_btn.clicked.connect(lambda: self._apply_template(config.PROVIDER_OPENAI))
        template_grid.addWidget(openai_template_btn)

        # Claude 按钮
        claude_template_btn = QPushButton("Claude")
        claude_template_btn.setObjectName("templateButton")
        claude_template_btn.setFixedHeight(36)  # 适中高度，宽度自适应
        claude_template_btn.clicked.connect(lambda: self._apply_template(config.PROVIDER_ANTHROPIC))
        template_grid.addWidget(claude_template_btn)

        # Gemini 按钮
        gemini_template_btn = QPushButton("Gemini")
        gemini_template_btn.setObjectName("templateButton")
        gemini_template_btn.setFixedHeight(36)  # 适中高度，宽度自适应
        gemini_template_btn.clicked.connect(lambda: self._apply_template(config.PROVIDER_GOOGLE))
        template_grid.addWidget(gemini_template_btn)

        # DeepSeek 按钮
        deepseek_template_btn = QPushButton("DeepSeek")
        deepseek_template_btn.setObjectName("templateButton")
        deepseek_template_btn.setFixedHeight(36)  # 适中高度，宽度自适应
        deepseek_template_btn.clicked.connect(lambda: self._apply_template(config.PROVIDER_DEEPSEEK))
        template_grid.addWidget(deepseek_template_btn)
        template_layout.addLayout(template_grid)

        panel_layout.addWidget(template_group)

        # 操作按钮 - 只保留添加和删除按钮，优化空间
        buttons_container = QWidget()
        buttons_container.setMaximumHeight(85)  # 减少高度
        buttons_layout = QVBoxLayout(buttons_container)
        buttons_layout.setSpacing(10)  # 适中的按钮间距
        buttons_layout.setContentsMargins(0, 5, 0, 5)  # 减少上下边距

        add_button = QPushButton("添加新的配置")
        add_button.setObjectName("addProfileButton")
        add_button.setMinimumHeight(32)  # 稍微减小高度
        add_button.clicked.connect(self._add_profile)
        buttons_layout.addWidget(add_button)

        delete_button = QPushButton("删除当前配置")
        delete_button.setObjectName("deleteProfileButton")
        delete_button.setMinimumHeight(32)  # 稍微减小高度
        delete_button.clicked.connect(self._delete_profile)
        buttons_layout.addWidget(delete_button)

        panel_layout.addWidget(buttons_container)
        panel_layout.addStretch()

        return panel

    def _create_config_panel(self) -> QWidget:
        """创建右侧配置编辑面板 - 优化布局和组件尺寸"""
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setSpacing(10)  # 压缩间距，为思考模式滑块腾出空间

        # 配置详情组 - 增大字体和组件尺寸
        config_group = QGroupBox("配置详情")
        config_group.setObjectName("configDetailsGroup")
        # 移除固定高度，让GroupBox根据内容自动调整高度

        config_form = QFormLayout(config_group)
        config_form.setSpacing(12)  # 压缩行间距
        config_form.setVerticalSpacing(14)  # 压缩垂直间距
        config_form.setLabelAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)  # 标签垂直居中并右对齐

        # 设置Form的边距，避免内容贴边
        config_form.setContentsMargins(15, 15, 15, 15)  # 压缩上下边距

        # 配置名称 - 使用CustomLabel保持与主界面一致
        profile_name_label = CustomLabel("配置名称:")
        profile_name_label.setFont(QFont('楷体', 14, QFont.Weight.Bold))
        profile_name_label.setMinimumHeight(36)  # 设置与输入框相同的最小高度
        profile_name_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)  # 确保标签垂直居中右对齐
        self.profile_name_edit = QLineEdit()
        self.profile_name_edit.setMinimumHeight(36)
        config_form.addRow(profile_name_label, self.profile_name_edit)

        # API格式选择 (替代原来的提供商选择)
        self.api_format_combo = QComboBox()
        self.api_format_combo.setMinimumHeight(36)
        self.api_format_combo.addItems([
            "OpenAI兼容", "Claude格式", "Gemini格式", "自动检测"
        ])
        self.api_format_combo.setCurrentText("OpenAI兼容")  # 默认OpenAI兼容
        self.api_format_combo.setToolTip("选择API格式：\n• OpenAI兼容：/v1/chat/completions (DeepSeek, OpenAI等)\n• Claude格式：/v1/messages (Anthropic Claude等)\n• Gemini格式：/v1beta/models/{model}:generateContent (Google Gemini等)\n• 自动检测：根据URL自动推断格式")

        self.api_format_label = CustomLabel("API格式:")
        self.api_format_label.setFont(QFont('楷体', 14, QFont.Weight.Bold))
        self.api_format_label.setMinimumHeight(36)
        self.api_format_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        config_form.addRow(self.api_format_label, self.api_format_combo)

        # API URL
        self.api_url_edit = QLineEdit()
        self.api_url_edit.setMinimumHeight(36)
        self.api_url_edit.setCursorPosition(0)  # 确保光标可见
        self.api_url_edit.setStyleSheet("""
            QLineEdit {
                color: #FFFFFF;
                font-size: 13pt;
                background-color: rgba(255, 255, 255, 60);
                border: 1px solid rgba(120, 195, 225, 140);
                border-radius: 6px;
                padding: 10px 10px;
            }
            QLineEdit:focus {
                border: 2px solid rgba(120, 195, 225, 220);
                background-color: rgba(255, 255, 255, 80);
            }
        """)

        # 设置动态悬浮提示
        self._update_api_url_tooltip()

        api_url_label = CustomLabel("API地址:")
        api_url_label.setFont(QFont('楷体', 14, QFont.Weight.Bold))
        api_url_label.setMinimumHeight(36)  # 设置与输入框相同的最小高度
        api_url_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)  # 确保标签垂直居中右对齐
        config_form.addRow(api_url_label, self.api_url_edit)

        # 模型名称
        model_layout = QHBoxLayout()
        model_layout.setSpacing(10)
        self.model_name_combo = QComboBox()
        self.model_name_combo.setEditable(True)
        self.model_name_combo.setMinimumHeight(36)
        model_layout.addWidget(self.model_name_combo, 3)  # 3:1比例

        self.fetch_models_button = QPushButton("获取模型")
        self.fetch_models_button.setObjectName("fetchModelsButton")
        self.fetch_models_button.clicked.connect(self._fetch_models)
        self.fetch_models_button.setMinimumWidth(80)
        self.fetch_models_button.setMinimumHeight(42)
        self.fetch_models_button.setFixedHeight(42)
        self.fetch_models_button.setStyleSheet("margin-top: 3px;")  # 向下偏移3px
        model_layout.addWidget(self.fetch_models_button, 1)

        model_label = CustomLabel("模型:")
        model_label.setFont(QFont('楷体', 14, QFont.Weight.Bold))
        model_label.setMinimumHeight(36)  # 设置与输入框相同的最小高度
        model_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)  # 确保标签垂直居中右对齐
        config_form.addRow(model_label, model_layout)

        # API Key - 使用更简单的方法
        api_key_layout = QHBoxLayout()
        api_key_layout.setSpacing(5)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setMinimumHeight(42)  # 增加高度
        self.api_key_edit.setFixedHeight(42)
        self.api_key_edit.setCursorPosition(0)  # 确保光标可见
        self.api_key_edit.setStyleSheet("""
            QLineEdit {
                color: #FFFFFF;
                font-size: 13pt;
                background-color: rgba(255, 255, 255, 60);
                border: 1px solid rgba(120, 195, 225, 140);
                border-radius: 6px;
                padding: 11px 10px;
            }
            QLineEdit:focus {
                border: 2px solid rgba(120, 195, 225, 220);
                background-color: rgba(255, 255, 255, 80);
            }
        """)
        api_key_layout.addWidget(self.api_key_edit)

        # 眼睛图标按钮
        self.api_key_toggle = QPushButton()
        self.api_key_toggle.setObjectName("apiKeyToggle")
        self.api_key_toggle.setFixedSize(42, 42)  # 与输入框高度完全匹配
        self.api_key_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.api_key_toggle.clicked.connect(self._toggle_api_key_visibility)
        # 设置眼睛图标
        self._update_eye_icon()
        api_key_layout.addWidget(self.api_key_toggle)

        api_key_label = CustomLabel("API Key:")
        api_key_label.setFont(QFont('楷体', 14, QFont.Weight.Bold))
        api_key_label.setMinimumHeight(42)  # API Key输入框是42px高度
        api_key_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)  # 确保标签垂直居中右对齐
        config_form.addRow(api_key_label, api_key_layout)

        # 温度设置 - 增大滑块和显示
        temp_layout = QHBoxLayout()
        temp_layout.setSpacing(15)
        self.temperature_slider = QSlider(Qt.Orientation.Horizontal)
        self.temperature_slider.setRange(0, 100)
        self.temperature_slider.setValue(20)  # 默认0.2
        self.temperature_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.temperature_slider.setTickInterval(10)
        self.temperature_slider.setMinimumHeight(36)

        self.temperature_value_label = QLabel("0.2")
        self.temperature_value_label.setMinimumWidth(50)
        self.temperature_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.temperature_value_label.setMinimumHeight(32)
        self.temperature_value_label.setObjectName("temperatureValueLabel")
        self.temperature_value_label.setStyleSheet("""
            QLabel#temperatureValueLabel {
                color: white;
                font-size: 13pt;
                font-weight: bold;
                background: transparent;
            }
            QLabel#temperatureValueLabel:disabled {
                color: rgba(160, 160, 160, 120);
            }
        """)  # 设置为白色
        temp_layout.addWidget(self.temperature_slider, 4)
        temp_layout.addWidget(self.temperature_value_label, 1)
        temp_label = CustomLabel("温度:")
        temp_label.setFont(QFont('楷体', 14, QFont.Weight.Bold))
        temp_label.setMinimumHeight(36)  # 设置与滑块相同的最小高度
        temp_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)  # 确保标签垂直居中右对齐
        config_form.addRow(temp_label, temp_layout)

        # 思考模式设置 - 三档滑块 (0=关闭, 1=高, 2=最大)
        thinking_layout = QHBoxLayout()
        thinking_layout.setSpacing(15)
        self.thinking_slider = QSlider(Qt.Orientation.Horizontal)
        self.thinking_slider.setRange(0, 2)
        self.thinking_slider.setValue(0)  # 默认关闭
        self.thinking_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.thinking_slider.setTickInterval(1)
        self.thinking_slider.setMinimumHeight(36)

        self.thinking_value_label = QLabel("关闭")
        self.thinking_value_label.setMinimumWidth(50)
        self.thinking_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thinking_value_label.setMinimumHeight(32)
        self.thinking_value_label.setObjectName("thinkingValueLabel")
        self.thinking_value_label.setStyleSheet("""
            QLabel#thinkingValueLabel {
                color: white !important;
                font-size: 13pt;
                font-weight: bold;
                background: transparent;
            }
        """)
        thinking_layout.addWidget(self.thinking_slider, 4)
        thinking_layout.addWidget(self.thinking_value_label, 1)
        thinking_label = CustomLabel("思考模式:")
        thinking_label.setFont(QFont('楷体', 14, QFont.Weight.Bold))
        thinking_label.setMinimumHeight(36)
        thinking_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        config_form.addRow(thinking_label, thinking_layout)

        panel_layout.addWidget(config_group)

        # 操作按钮组 - 设为默认和测试连接（横向排列节省空间）
        action_group = QGroupBox("操作")
        action_layout = QHBoxLayout(action_group)
        action_layout.setSpacing(12)
        action_layout.setContentsMargins(15, 8, 15, 8)

        # 设为默认按钮
        set_default_button = QPushButton("设为默认")
        set_default_button.setObjectName("setDefaultButton")
        set_default_button.setMinimumHeight(38)
        set_default_button.clicked.connect(self._set_default_profile)
        action_layout.addWidget(set_default_button)

        # 测试连接按钮
        self.test_connection_button = QPushButton("测试连接")
        self.test_connection_button.setObjectName("testConnectionButton")
        self.test_connection_button.clicked.connect(self._test_connection)
        self.test_connection_button.setMinimumHeight(38)
        action_layout.addWidget(self.test_connection_button)

        panel_layout.addWidget(action_group)

        # 底部按钮组 - 保存和取消按钮
        button_container = QWidget()
        button_container.setMaximumHeight(50)  # 减少高度，为配置详情区域腾出空间
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(15)

        button_layout.addStretch()

        save_button = QPushButton("保存配置")
        save_button.setObjectName("dialogSaveButton")
        save_button.setMinimumWidth(120)
        save_button.setMinimumHeight(40)
        save_button.clicked.connect(self.accept)
        button_layout.addWidget(save_button)

        cancel_button = QPushButton("取消")
        cancel_button.setObjectName("dialogCancelButton")
        cancel_button.setMinimumWidth(100)
        cancel_button.setMinimumHeight(40)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        panel_layout.addWidget(button_container)

        return panel

    def _update_eye_icon(self):
        """更新眼睛图标为自定义图片"""
        is_visible = self.api_key_edit.echoMode() == QLineEdit.EchoMode.Normal

        if is_visible:
            # 显示状态 - 使用睁眼图片
            eye_path = resource_path('eye-Visible.png')
        else:
            # 隐藏状态 - 使用闭眼图片
            eye_path = resource_path('eye-Invisible.png')

        if eye_path and os.path.exists(eye_path):
            self.api_key_toggle.setIcon(QIcon(eye_path))
            self.api_key_toggle.setIconSize(QSize(20, 20))
            self.api_key_toggle.setText("")  # 清除文本
        else:
            # 如果图片不存在，使用emoji作为后备
            self.api_key_toggle.setText("🙈" if is_visible else "👁")

    def _toggle_api_key_visibility(self):
        """切换API Key的可见性"""
        if self.api_key_edit.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)

        # 更新眼睛图标
        self._update_eye_icon()

    def _apply_styles(self):
        """应用样式 - 优化颜色和字体，提升可读性和美观度"""
        # 获取箭头图标路径
        qss_image_up_arrow = "none"
        qss_image_down_arrow = "none"
        up_arrow_path_str = resource_path('up_arrow.png')
        down_arrow_path_str = resource_path('dropdown_arrow.png')

        if up_arrow_path_str and os.path.exists(up_arrow_path_str):
            qss_image_up_arrow = f"url('{up_arrow_path_str.replace(os.sep, '/')}')"
        if down_arrow_path_str and os.path.exists(down_arrow_path_str):
            qss_image_down_arrow = f"url('{down_arrow_path_str.replace(os.sep, '/')}')"

        style = f"""
            QWidget#llmSettingsDialogContainer {{
                background-color: rgba(60, 60, 80, 220);
                border-radius: 10px;
            }}
            CustomLabel {{
                background-color: transparent;
            }}
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(85, 180, 212, 180), stop:1 rgba(65, 140, 190, 200));
                color: white;
                border: 1px solid rgba(120, 195, 225, 150);
                border-radius: 8px;
                font-family: '楷体'; font-weight: bold; font-size: 13pt;
                padding: 10px 20px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(105, 200, 232, 220), stop:1 rgba(85, 160, 210, 230));
                border: 1px solid rgba(140, 215, 245, 200);
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(65, 160, 192, 180), stop:1 rgba(45, 120, 170, 200));
            }}

            QPushButton#dialogCloseButton {{
                background: rgba(255, 99, 71, 120);
                border: none;
                border-radius: 15px;
                padding: 0px;
                min-width: 30px; max-width:30px;
                min-height:30px; max-height:30px;
            }}
            QPushButton#dialogCloseButton:hover {{
                background: rgba(255, 69, 58, 180);
                border-radius: 15px;
            }}

            QPushButton#apiKeyToggle {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(150, 150, 150, 160), stop:1 rgba(120, 120, 120, 170));
                border: 1px solid rgba(170, 170, 170, 140);
                border-radius: 8px;
                font-size: 11pt;
                padding: 8px 16px;
                margin-top: 3px;
            }}
            QPushButton#apiKeyToggle:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(170, 170, 170, 190), stop:1 rgba(140, 140, 140, 200));
            }}

            QPushButton#dialogSaveButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(75, 185, 125, 200), stop:1 rgba(55, 155, 105, 210));
                border: 1px solid rgba(95, 205, 145, 180);
                font-size: 14pt;
            }}
            QPushButton#dialogSaveButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(95, 205, 145, 230), stop:1 rgba(75, 175, 125, 240));
            }}

            QPushButton#dialogCancelButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(180, 120, 90, 180), stop:1 rgba(160, 100, 70, 190));
                border: 1px solid rgba(200, 140, 110, 150);
                font-size: 14pt;
            }}
            QPushButton#dialogCancelButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(200, 140, 110, 210), stop:1 rgba(180, 120, 90, 220));
            }}

            QPushButton#templateButton, QPushButton#setDefaultButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(95, 155, 195, 160), stop:1 rgba(75, 125, 165, 170));
                font-size: 11pt;
                padding: 8px 16px;
            }}
            QPushButton#templateButton:hover, QPushButton#setDefaultButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(115, 175, 215, 200), stop:1 rgba(95, 145, 185, 210));
            }}

            QPushButton#addProfileButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(75, 185, 125, 200), stop:1 rgba(55, 155, 105, 210));
                font-size: 11pt;
                padding: 8px 16px;
                border: 1px solid rgba(95, 205, 145, 180);
            }}
            QPushButton#addProfileButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(95, 205, 145, 230), stop:1 rgba(75, 175, 125, 240));
                border: 1px solid rgba(115, 225, 165, 200);
            }}

            QPushButton#deleteProfileButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(180, 80, 80, 200), stop:1 rgba(160, 60, 60, 210));
                font-size: 11pt;
                padding: 8px 16px;
                border: 1px solid rgba(200, 100, 100, 180);
            }}
            QPushButton#deleteProfileButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(200, 100, 100, 230), stop:1 rgba(180, 80, 80, 240));
                border: 1px solid rgba(220, 120, 120, 200);
            }}

            QPushButton#testConnectionButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 185, 65, 180), stop:1 rgba(235, 155, 45, 190));
                border: 1px solid rgba(255, 205, 125, 160);
                font-size: 13pt;
            }}
            QPushButton#testConnectionButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 205, 85, 210), stop:1 rgba(235, 175, 65, 220));
            }}

            QPushButton#fetchModelsButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(150, 150, 150, 160), stop:1 rgba(120, 120, 120, 170));
                border: 1px solid rgba(170, 170, 170, 140);
                font-size: 11pt;
            }}
            QPushButton#fetchModelsButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(170, 170, 170, 190), stop:1 rgba(140, 140, 140, 200));
            }}

            QSlider::groove:horizontal {{
                border: 1px solid rgba(140, 140, 140, 180);
                background: rgba(255, 255, 255, 80);
                height: 12px;
                border-radius: 6px;
            }}
            QSlider::handle:horizontal {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #B0B0B0, stop:1 #808080);
                border: 2px solid #606060;
                width: 24px;
                margin: -6px 0;
                border-radius: 12px;
            }}
            QSlider::sub-page:horizontal {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(75, 185, 125, 180), stop:1 rgba(85, 195, 220, 190));
                border: 1px solid rgba(140, 140, 140, 180);
                height: 12px;
                border-radius: 6px;
            }}
            QSlider::groove:horizontal:disabled {{
                background: rgba(180, 180, 180, 60);
                border: 1px solid rgba(140, 140, 140, 100);
            }}
            QSlider::handle:horizontal:disabled {{
                background: rgba(160, 160, 160, 120);
                border: 2px solid rgba(120, 120, 120, 100);
            }}
            QSlider::sub-page:horizontal:disabled {{
                background: rgba(160, 160, 160, 80);
                border: 1px solid rgba(140, 140, 140, 100);
            }}

            QSpinBox, QDoubleSpinBox {{
                background-color: rgba(255, 255, 255, 60);
                color: #F5F5F5;
                border: 1px solid rgba(120, 195, 225, 140);
                border-radius: 6px;
                font-family: '楷体';
                font-size: 13pt;
                min-height: 36px;
                padding-top: 3px;
                padding-bottom: 3px;
                padding-left: 10px;
                padding-right: 5px;
            }}

            QLineEdit, QComboBox, QTextEdit {{
                background-color: rgba(255, 255, 255, 60);
                color: #F5F5F5;
                border: 1px solid rgba(120, 195, 225, 140);
                border-radius: 6px;
                font-family: '楷体';
                font-size: 13pt;
                padding: 12px 10px;
                min-height: 22px;
                selection-background-color: rgba(120, 195, 225, 200);
                line-height: 1.2;
            }}

            QLineEdit {{
                color: #FFFFFF;
                selection-background-color: rgba(120, 195, 225, 200);
            }}

            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
                border: 2px solid rgba(120, 195, 225, 220);
                background-color: rgba(255, 255, 255, 80);
            }}

            QComboBox::drop-down {{
                subcontrol-origin: padding;
                width: 30px;
                border-left: 1px solid rgba(120, 195, 225, 140);
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background-color: rgba(120, 195, 225, 120);
            }}

            QComboBox::down-arrow {{
                image: {qss_image_down_arrow};
                width: 12px;
                height: 12px;
            }}

            QComboBox QAbstractItemView {{
                background-color: rgba(50, 55, 70, 250);
                color: #F5F5F5;
                border: 1px solid rgba(120, 195, 225, 140);
                border-radius: 6px;
                selection-background-color: rgba(120, 195, 225, 200);
                font-family: '楷体';
                font-size: 12pt;
                padding: 5px;
            }}

            QListWidget#profileList {{
                border: 1px solid rgba(120, 195, 225, 140);
                border-radius: 6px;
                padding: 8px;
                background-color: rgba(255, 255, 255, 60);
                font-family: '楷体';
                font-size: 13pt;
                outline: none;
            }}

            QListWidget#profileList::item {{
                padding: 12px 10px;
                margin: 3px 0;
                border-radius: 6px;
                color: #F5F5F5;
                background-color: transparent;
                outline: none;
                border: none;
            }}

            QListWidget#profileList::item:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(120, 195, 225, 200), stop:1 rgba(85, 160, 190, 180));
                color: white;
            }}

            QListWidget#profileList::item:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(120, 195, 225, 120), stop:1 rgba(85, 160, 190, 100));
            }}

            QGroupBox {{
                font-weight: bold;
                font-size: 16px;
                color: #F5F5F5;
                border: 2px solid rgba(120, 195, 225, 140);
                border-radius: 10px;
                margin: 8px 0px;
                padding-top: 15px;
                font-family: '楷体';
                background-color: rgba(255, 255, 255, 20);
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                color: #F5F5F5;
            }}

            QGroupBox#configDetailsGroup::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                color: #FFFFFF;  /* 改为白色 */
                font: bold 15pt '楷体';
            }}

            QCheckBox {{
                font-family: '楷体';
                font-size: 13pt;
                color: #F5F5F5;
                spacing: 12px;
            }}

            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
                border: 2px solid rgba(120, 195, 225, 140);
                border-radius: 5px;
                background-color: rgba(255, 255, 255, 60);
            }}

            QCheckBox::indicator:checked {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(120, 195, 225, 200), stop:1 rgba(85, 160, 190, 180));
                border-color: rgba(120, 195, 225, 220);
            }}

            QCheckBox::indicator:hover {{
                border-color: rgba(120, 195, 225, 220);
            }}

            QSplitter::handle {{
                background-color: rgba(120, 195, 225, 100);
                width: 3px;
                border-radius: 1px;
            }}

            QSplitter::handle:hover {{
                background-color: rgba(120, 195, 225, 180);
            }}
        """

        self.setStyleSheet(style)

    def _connect_signals(self):
        """连接信号"""
        # 模型列表选择变化
        self.profile_list.currentItemChanged.connect(self._on_profile_selected)

        # 提供商变化 - 为了向后兼容性保留连接，但provider_combo已从UI移除
        # 只有当provider_combo不是None时才连接信号
        if hasattr(self, 'provider_combo') and self.provider_combo is not None:
            self.provider_combo.currentTextChanged.connect(self._on_provider_changed)

        # 温度滑块变化
        self.temperature_slider.valueChanged.connect(self._on_temperature_changed)

        # 思考模式滑块变化
        self.thinking_slider.valueChanged.connect(self._on_thinking_changed)

        # API格式变化 - 更新悬浮提示
        self.api_format_combo.currentTextChanged.connect(self._update_api_url_tooltip)

    def _load_profiles_to_ui(self):
        """加载配置到UI"""
        # 获取所有配置
        self.profiles = config.get_all_llm_profiles(self.config)

        # 获取当前配置ID
        self.current_profile_id = self.config.get(config.CURRENT_PROFILE_ID_KEY, config.DEFAULT_CURRENT_PROFILE_ID)

        # 清空列表
        self.profile_list.clear()

        # 添加配置到列表
        for profile in self.profiles:
            item = QListWidgetItem(profile["name"])
            item.setData(Qt.ItemDataRole.UserRole, profile["id"])

            # 标记默认配置
            if profile.get("is_default", False):
                item.setText(f"{profile['name']} (默认)")
                font = item.font()
                font.setBold(True)
                item.setFont(font)

            # 标记当前配置
            if profile["id"] == self.current_profile_id:
                item.setBackground(QColor(135, 206, 235, 100))

            self.profile_list.addItem(item)

        # 优先选择默认配置，如果没有默认配置才选择当前配置
        default_item = None
        current_item = None

        for i in range(self.profile_list.count()):
            item = self.profile_list.item(i)
            profile_id = item.data(Qt.ItemDataRole.UserRole)

            # 查找默认配置
            if not default_item:
                # 从profiles数组中查找对应的配置
                for profile in self.profiles:
                    if profile["id"] == profile_id and profile.get("is_default", False):
                        default_item = item
                        break

            # 查找当前配置
            if not current_item and profile_id == self.current_profile_id:
                current_item = item

        # 优先选择默认配置
        selected_item = default_item or current_item
        if selected_item:
            self.profile_list.setCurrentItem(selected_item)
            self._on_profile_selected(selected_item, None)
        # 如果都没有找到但有配置列表，选择第一个
        elif self.profile_list.count() > 0:
            first_item = self.profile_list.item(0)
            self.profile_list.setCurrentItem(first_item)
            self._on_profile_selected(first_item, None)

    def _on_profile_selected(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        """处理配置选择变化"""
        if not current_item:
            return

        profile_id = current_item.data(Qt.ItemDataRole.UserRole)

        # 查找配置
        profile = None
        for p in self.profiles:
            if p["id"] == profile_id:
                profile = p
                break

        if profile:
            # 更新当前配置ID（仅用于对话框内部，不改变全局当前活跃配置）
            self.current_profile_id = profile_id
            # 注意：不要在这里更新全局的CURRENT_PROFILE_ID_KEY
            # 因为用户在LLM高级设置中选择配置不应该改变全局的当前活跃配置

            # 加载配置到UI
            self.profile_name_edit.setText(profile.get("name", ""))
            # 移除provider_combo的引用，为了向后兼容性保留条件检查
            if hasattr(self, 'provider_combo') and self.provider_combo is not None:
                self.provider_combo.setCurrentText(profile.get("provider", ""))
            self.api_url_edit.setText(profile.get("api_base_url", ""))
            self.api_key_edit.setText(profile.get("api_key", ""))

            # 加载API格式
            api_format = profile.get("api_format", config.API_FORMAT_AUTO)
            api_format_reverse_map = {
                config.API_FORMAT_AUTO: "自动检测",
                config.API_FORMAT_OPENAI: "OpenAI兼容",
                config.API_FORMAT_CLAUDE: "Claude格式",
                config.API_FORMAT_GEMINI: "Gemini格式"
            }
            api_format_text = api_format_reverse_map.get(api_format, "自动检测")
            self.api_format_combo.setCurrentText(api_format_text)

            # 判断是否为自定义配置（通过检查provider是否为空或者"自定义"）
            is_custom_config = (not profile.get("provider") or profile.get("provider") == "自定义")
            self.api_format_combo.setEnabled(is_custom_config)

            temperature = profile.get("temperature", 0.2)
            self.temperature_slider.setValue(int(temperature * 100))
            self.temperature_value_label.setText(f"{temperature:.1f}")

            # 加载思考模式
            thinking_level = profile.get("thinking_level", 0)
            self.thinking_slider.setValue(thinking_level)
            thinking_labels = {0: "关闭", 1: "高", 2: "最大"}
            self.thinking_value_label.setText(thinking_labels.get(thinking_level, "关闭"))

            # 同步温度滑块的禁用状态
            thinking_on = thinking_level > 0
            self.temperature_slider.setEnabled(not thinking_on)
            self.temperature_value_label.setEnabled(not thinking_on)
            if thinking_on:
                self.temperature_slider.setToolTip("思考模式下温度参数不生效")
                self.temperature_value_label.setText("禁用")
            else:
                self.temperature_slider.setToolTip("")

            # 更新API地址的悬浮提示
            self._update_api_url_tooltip()

            # 加载保存的模型列表
            available_models = profile.get("available_models", [])
            self.model_name_combo.clear()
            if available_models:
                # 如果有保存的模型列表，加载到下拉框
                for model in available_models:
                    self.model_name_combo.addItem(model)
                # 设置当前选择的模型
                current_model = profile.get("model_name", "")
                if current_model and current_model in available_models:
                    self.model_name_combo.setCurrentText(current_model)
                elif available_models:
                    self.model_name_combo.setCurrentText(available_models[0])
            else:
                # 如果没有保存的模型列表，只设置当前模型
                current_model = profile.get("model_name", "")
                if current_model:
                    self.model_name_combo.addItem(current_model)
                    self.model_name_combo.setCurrentText(current_model)

    def _on_provider_changed(self, provider_name: str):
        """处理提供商变化 - 保持向后兼容性，现在不再使用"""
        # 为了向后兼容性保留此方法，但不再执行任何操作
        # 因为移除了provider选择器，这个方法不会被调用
        pass

    def _update_api_url_tooltip(self):
        """根据当前选择的API格式更新悬浮提示"""
        current_format = self.api_format_combo.currentText()

        if current_format == "OpenAI兼容":
            tooltip_text = (
                "OpenAI兼容格式\n"
                "• 输入示例: https://api.openai.com\n"
                "• 最终请求: https://api.openai.com/v1/chat/completions\n"
                "• 适用于: DeepSeek, OpenAI, 大多数兼容API\n"
                "• 完整路径: https://api.openai.com/v1/chat/completions# (使用完整路径)"
            )
        elif current_format == "Claude格式":
            tooltip_text = (
                "Claude格式\n"
                "• 输入示例: https://api.anthropic.com\n"
                "• 最终请求: https://api.anthropic.com/v1/messages\n"
                "• 适用于: Anthropic Claude, Claude兼容API\n"
                "• 完整路径: https://api.anthropic.com/v1/messages# (使用完整路径)"
            )
        elif current_format == "Gemini格式":
            tooltip_text = (
                "Gemini格式\n"
                "• 输入示例: https://generativelanguage.googleapis.com\n"
                "• 最终请求: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent\n"
                "• 适用于: Google Gemini, Gemini兼容API\n"
                "• 完整路径: https://generativelanguage.googleapis.com/v1beta/models/{model}# (注意：{model}会被替换)"
            )
        elif current_format == "自动检测":
            tooltip_text = (
                "自动检测格式\n"
                "• 建议: 官方API使用自动检测，第三方API手动指定格式\n"
                "• 完整路径: 在任何完整URL后添加 '#' 标记以跳过路径构建"
            )
        else:
            tooltip_text = "请选择API格式以查看详细信息"

        self.api_url_edit.setToolTip(tooltip_text)

    def _on_temperature_changed(self, value: int):
        """处理温度滑块变化"""
        temperature = value / 100.0
        self.temperature_value_label.setText(f"{temperature:.1f}")

    def _on_thinking_changed(self, value: int):
        """处理思考模式滑块变化"""
        labels = {0: "关闭", 1: "高", 2: "最大"}
        self.thinking_value_label.setText(labels.get(value, "关闭"))

        # 思考模式开启时禁用温度滑块（思考模式下温度参数不生效）
        thinking_on = value > 0
        self.temperature_slider.setEnabled(not thinking_on)
        self.temperature_value_label.setEnabled(not thinking_on)
        if thinking_on:
            self.temperature_slider.setToolTip("思考模式下温度参数不生效")
            self.temperature_value_label.setText("禁用")
        else:
            self.temperature_slider.setToolTip("")
            self.temperature_value_label.setText(f"{self.temperature_slider.value() / 100.0:.1f}")

    def _add_profile(self):
        """添加新配置"""
        import uuid

        # 创建新配置字典
        profile_name = self._generate_unique_name("新配置")
        new_profile = {
            "id": f"custom_{uuid.uuid4().hex[:8]}",
            "name": profile_name,
            "provider": "自定义",
            "api_base_url": "",
            "model_name": "",
            "api_key": "",
            "temperature": 0.2,
            "is_default": False,
            "custom_headers": {},
            "api_format": config.API_FORMAT_AUTO,  # 默认自动检测
            "thinking_level": 0  # 默认关闭思考模式
        }

        # 使用config模块添加新配置
        self.config = config.add_llm_profile(self.config, new_profile)

        # 重新加载配置列表
        self._load_profiles_to_ui()

        # 选中新创建的配置
        for i in range(self.profile_list.count()):
            item = self.profile_list.item(i)
            profile_id = item.data(Qt.ItemDataRole.UserRole)
            # 从所有配置中查找指定ID的配置
            profiles = config.get_all_llm_profiles(self.config)
            profile = next((p for p in profiles if p.get("id") == profile_id), None)
            if profile and profile.get("name") == profile_name:
                self.profile_list.setCurrentItem(item)
                # 触发选择事件来加载配置
                self._on_profile_selected(item, None)
                break

    def _delete_profile(self):
        """删除当前配置"""
        current_item = self.profile_list.currentItem()
        if not current_item:
            return

        profile_id = current_item.data(Qt.ItemDataRole.UserRole)

        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除", "确定要删除此配置吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 从配置中删除
                self.config = config.delete_llm_profile(self.config, profile_id)
                # 立即发出信号保存配置到文件
                self.settings_applied.emit(self.config)
                # 重新加载
                self._load_profiles_to_ui()
            except ValueError as e:
                QMessageBox.warning(self, "删除失败", str(e))

    def _save_current_profile(self):
        """保存当前配置到存储"""
        current_item = self.profile_list.currentItem()
        if not current_item:
            return False

        profile_id = current_item.data(Qt.ItemDataRole.UserRole)

        # 查找配置
        for i, profile in enumerate(self.profiles):
            if profile["id"] == profile_id:
                # 获取API格式
                api_format_text = self.api_format_combo.currentText()
                api_format_map = {
                    "自动检测": config.API_FORMAT_AUTO,
                    "OpenAI兼容": config.API_FORMAT_OPENAI,
                    "Claude格式": config.API_FORMAT_CLAUDE,
                    "Gemini格式": config.API_FORMAT_GEMINI
                }
                api_format = api_format_map.get(api_format_text, config.API_FORMAT_AUTO)

                # 更新配置
                # 保持向后兼容性：如果原配置有provider字段且不是空，保留它
                original_provider = profile.get("provider", "")

                self.profiles[i] = {
                    "id": profile_id,
                    "name": self.profile_name_edit.text().strip() or profile["name"],
                    "provider": original_provider,  # 保持原有provider不变，保持向后兼容
                    "api_base_url": self.api_url_edit.text().strip(),
                    "model_name": self.model_name_combo.currentText().strip(),
                    "api_key": self.api_key_edit.text().strip(),
                    "temperature": self.temperature_slider.value() / 100.0,
                    "is_default": profile.get("is_default", False),
                    "custom_headers": profile.get("custom_headers", {}),
                    "available_models": profile.get("available_models", []),  # 保存模型列表
                    "api_format": api_format,  # 保存API格式
                    "thinking_level": self.thinking_slider.value()  # 保存思考模式等级
                }

                # 注意：不要在这里更新全局的CURRENT_PROFILE_ID_KEY
                # 保存配置不应该改变全局的当前活跃配置

                # 保存配置
                self.config[config.LLM_PROFILES_KEY] = {"profiles": self.profiles}
                return True

        return False

    def _set_default_profile(self):
        """设置当前配置为默认（即当前使用的配置）"""
        current_item = self.profile_list.currentItem()
        if not current_item:
            return

        profile_id = current_item.data(Qt.ItemDataRole.UserRole)

        # 查找原始配置
        original_profile = None
        for profile in self.profiles:
            if profile["id"] == profile_id:
                original_profile = profile
                break

        # 检查API Key是否有修改
        if original_profile and self.api_key_edit.text().strip() != original_profile.get("api_key", ""):
            reply = QMessageBox.question(
                self,
                "未保存的修改",
                f"配置 '{original_profile.get('name', profile_id)}' 有未保存的API Key修改。\n\n"
                "是否要在设置为默认配置之前保存这些修改？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                if not self._save_current_profile():
                    QMessageBox.warning(self, "提示", "无法保存当前配置")
                    return
            # 如果用户选择不保存，则直接继续设置默认配置，不保存当前的UI修改

        # 获取配置名称用于显示（在重新加载UI之前）
        profile_name = current_item.text().replace(" (默认)", "")  # 移除旧的默认标识

        # 检查主窗口的"记住API Key"复选框状态
        should_remember_api_key = True
        if self.parent_window and hasattr(self.parent_window, 'remember_api_key_checkbox'):
            should_remember_api_key = self.parent_window.remember_api_key_checkbox.isChecked()

        # 如果主窗口没有勾选"记住API Key"，则清除当前默认配置的API Key
        if not should_remember_api_key:
            # 找到当前的默认配置并清除其API Key
            for i, profile in enumerate(self.profiles):
                if profile.get("is_default", False):
                    self.profiles[i]["api_key"] = ""
                    break

        # 设置为默认配置（当前配置 = 默认配置）
        self.config = config.set_default_llm_profile(self.config, profile_id)

        # 同时更新当前活跃配置ID（统一概念：当前配置就是默认配置）
        self.config[config.CURRENT_PROFILE_ID_KEY] = profile_id

        # 发射信号保存配置到文件
        self.settings_applied.emit(self.config)

        # 重新加载UI
        self._load_profiles_to_ui()

        # 重新选择刚刚设为默认的配置项
        for i in range(self.profile_list.count()):
            item = self.profile_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == profile_id:
                self.profile_list.setCurrentItem(item)
                self._on_profile_selected(item, None)
                break

        # 显示成功提示（统一概念）
        QMessageBox.information(self, "设置成功", f"已将「{profile_name}」设为默认配置（当前使用）")

        # 输出日志到主界面
        if self.parent_window and hasattr(self.parent_window, 'log_message'):
            if should_remember_api_key:
                self.parent_window.log_message(f"✅ 已将「{profile_name}」设为默认配置")
            else:
                self.parent_window.log_message(f"✅ 已将「{profile_name}」设为默认配置（已清除旧配置的API Key）")

    def _generate_unique_name(self, name_prefix: str) -> str:
        """生成唯一的配置名称，避免重名"""
        import re
        profiles = config.get_all_llm_profiles(self.config)
        existing_names = [profile.get("name", "") for profile in profiles]

        # 首先检查基础名称是否可用
        if name_prefix not in existing_names:
            return name_prefix

        # 如果基础名称已存在，查找所有匹配的编号
        # 匹配格式：name_prefix(n) 其中n是数字
        pattern = re.compile(f'^{re.escape(name_prefix)}\\((\\d+)\\)$')
        max_num = 0
        has_numbered = False

        for name in existing_names:
            match = pattern.match(name)
            if match:
                has_numbered = True
                num = int(match.group(1))
                max_num = max(max_num, num)

        # 生成新的编号
        if has_numbered:
            new_num = max_num + 1
            return f"{name_prefix}({new_num})"
        else:
            # 如果没有编号版本，从(1)开始
            return f"{name_prefix}(1)"

    def _apply_template(self, provider: str):
        """应用提供商模板，创建新的配置"""
        templates = {
            config.PROVIDER_OPENAI: {
                "name_prefix": "新的OpenAI配置",
                "api_base_url": "https://api.openai.com",
                "model_name": "gpt-4o",  # 默认选择第一个模型
                "temperature": 0.2,
                "api_format": config.API_FORMAT_OPENAI,
                "default_models": [
                    "gpt-4o",
                    "gpt-4o-mini",
                    "gpt-4-turbo",
                    "gpt-3.5-turbo"
                ]
            },
            config.PROVIDER_ANTHROPIC: {
                "name_prefix": "新的Claude配置",
                "api_base_url": "https://api.anthropic.com",
                "model_name": "claude-sonnet-4-5-20250929",  # 默认选择第一个模型
                "temperature": 0.2,
                "api_format": config.API_FORMAT_CLAUDE,
                "default_models": [
                    "claude-sonnet-4-5-20250929",
                    "claude-opus-4-1-20250805",
                    "claude-haiku-4-5-20251001"
                ]
            },
            config.PROVIDER_GOOGLE: {
                "name_prefix": "新的Gemini配置",
                "api_base_url": "https://generativelanguage.googleapis.com",
                "model_name": "gemini-1.5-flash",  # 默认选择第一个模型
                "temperature": 0.2,
                "api_format": config.API_FORMAT_GEMINI,
                "default_models": [
                    "gemini-1.5-flash",
                    "gemini-1.5-pro",
                    "gemini-pro"
                ]
            },
            config.PROVIDER_DEEPSEEK: {
                "name_prefix": "新的DeepSeek配置",
                "api_base_url": "https://api.deepseek.com",
                "model_name": "deepseek-v4-flash",
                "temperature": 0.2,
                "api_format": config.API_FORMAT_OPENAI,
                "default_models": [
                    "deepseek-v4-flash",
                    "deepseek-v4-pro"
                ]
            }
        }

        if provider in templates:
            template = templates[provider]

            # 生成唯一的配置名称
            unique_name = self._generate_unique_name(template["name_prefix"])

            # 创建新的配置文件
            new_profile = {
                "id": f"template_{provider.lower()}_{uuid.uuid4().hex[:8]}",
                "name": unique_name,
                "provider": template.get("provider", ""),  # 保持向后兼容，可以为空
                "api_base_url": template["api_base_url"],
                "model_name": template["model_name"],  # 使用模板中的默认模型
                "api_key": "",  # API key为空，用户需要自己填写
                "temperature": template["temperature"],
                "available_models": template["default_models"],  # 使用模板中的默认模型列表
                "custom_headers": {},
                "api_format": template["api_format"],  # 新增API格式
                "thinking_level": 0  # 默认关闭思考模式
            }

            self.config = config.add_llm_profile(self.config, new_profile)
            new_profile_id = new_profile["id"]

            # 重新加载配置列表并选中新创建的配置
            self._load_profiles_to_ui()

            # 找到刚创建的配置并选中
            for i in range(self.profile_list.count()):
                item = self.profile_list.item(i)
                profile_id = item.data(Qt.ItemDataRole.UserRole)
                # 找到刚创建的配置并选中
                if profile_id == new_profile_id:
                    self.profile_list.setCurrentItem(item)
                    # 触发选择事件来加载配置
                    self._on_profile_selected(item, None)
                    break

    def _fetch_models(self):
        """获取模型列表"""
        # 安全检查：确保线程不存在或已完成
        if self.fetch_thread and self.fetch_thread.isRunning():
            return

        api_base_url = self.api_url_edit.text().strip()
        api_key = self.api_key_edit.text().strip()

        if not api_base_url or not api_key:
            QMessageBox.warning(self, "提示", "请先填写API地址和API Key")
            return

        # 获取当前选择的 API 格式，传递给 Worker
        api_format_text = self.api_format_combo.currentText()
        
        # 禁用获取按钮，显示获取中状态
        self.fetch_models_button.setEnabled(False)
        self.fetch_models_button.setText("⏳ 获取中...")
        
        # 创建工作线程 - 传递 API 格式文本
        self.fetch_thread = QThread()
        self.fetch_worker = ModelFetchWorker(api_base_url, api_key, api_format_text)
        self.fetch_worker.moveToThread(self.fetch_thread)

        # 连接信号
        self.fetch_thread.started.connect(self.fetch_worker.run)
        self.fetch_worker.finished.connect(self._on_models_fetched)
        self.fetch_worker.finished.connect(self.fetch_thread.quit)
        self.fetch_worker.finished.connect(self.fetch_worker.deleteLater)
        self.fetch_thread.finished.connect(self.fetch_thread.deleteLater)

        self.fetch_thread.start()

        # 设置30秒超时定时器
        self.fetch_timeout_timer = QTimer()
        self.fetch_timeout_timer.setSingleShot(True)
        self.fetch_timeout_timer.timeout.connect(self._on_fetch_timeout)
        self.fetch_timeout_timer.start(30000)  # 30秒

    def _on_fetch_timeout(self):
        """处理获取模型超时"""
        if self.fetch_thread and self.fetch_thread.isRunning():
            self.fetch_thread.quit()
            self.fetch_thread.wait(3000)  # 等待3秒让线程结束
            self.fetch_worker = None
            self.fetch_thread = None

            # 恢复获取按钮状态
            self.fetch_models_button.setEnabled(True)
            self.fetch_models_button.setText("获取模型")

            QMessageBox.warning(self, "超时", "获取模型列表超时，可能是网络连接问题或API服务器响应缓慢。请检查网络连接后重试。")

            # 输出超时日志到主界面
            if self.parent_window and hasattr(self.parent_window, 'log_message'):
                self.parent_window.log_message("⚠️ 获取模型列表超时")

    def _on_models_fetched(self, models: list, message: str):
        """处理获取到的模型列表"""
        try:
            # 停止超时定时器
            if hasattr(self, 'fetch_timeout_timer') and self.fetch_timeout_timer:
                self.fetch_timeout_timer.stop()
                self.fetch_timeout_timer.deleteLater()
                self.fetch_timeout_timer = None
            
            # 恢复获取按钮状态
            self.fetch_models_button.setEnabled(True)
            self.fetch_models_button.setText("获取模型")
            
            if models:
                # 清空当前模型列表
                self.model_name_combo.clear()

                # 添加获取到的模型
                for model in models:
                    self.model_name_combo.addItem(model)

                # 保存模型列表到当前配置
                current_item = self.profile_list.currentItem()
                if current_item:
                    profile_id = current_item.data(Qt.ItemDataRole.UserRole)

                    # 查找并更新配置中的模型列表
                    for i, profile in enumerate(self.profiles):
                        if profile["id"] == profile_id:
                            self.profiles[i]["available_models"] = models
                            # 保存配置
                            self.config[config.LLM_PROFILES_KEY] = {"profiles": self.profiles}
                            break

                QMessageBox.information(self, "成功", message)
            else:
                QMessageBox.warning(self, "失败", message)
        finally:
            # 清理线程引用
            self.fetch_worker = None
            self.fetch_thread = None

    def _test_connection(self):
        """测试连接"""
        if self.test_worker and self.test_thread and self.test_thread.isRunning():
            return

        api_key = self.api_key_edit.text().strip()
        api_base_url = self.api_url_edit.text().strip()
        model_name = self.model_name_combo.currentText().strip()
        temperature = self.temperature_slider.value() / 100.0

        if not api_key or not api_base_url or not model_name:
            QMessageBox.warning(self, "提示", "请先填写完整的配置信息")
            return

        # 获取当前选择的API格式
        api_format_text = self.api_format_combo.currentText()
        api_format_map = {
            "自动检测": config.API_FORMAT_AUTO,
            "OpenAI兼容": config.API_FORMAT_OPENAI,
            "Claude格式": config.API_FORMAT_CLAUDE,
            "Gemini格式": config.API_FORMAT_GEMINI
        }
        api_format = api_format_map.get(api_format_text, config.API_FORMAT_AUTO)

        # 检查模型列表是否为空（排除Claude，因为Claude是静态模型）
        current_item = self.profile_list.currentItem()
        if current_item:
            profile_id = current_item.data(Qt.ItemDataRole.UserRole)
            profiles = config.get_all_llm_profiles(self.config)
            current_profile = next((p for p in profiles if p.get("id") == profile_id), None)
            if current_profile:
                available_models = current_profile.get("available_models", [])
                # 如果模型列表为空且不是Claude格式，则提示用户先获取模型
                if not available_models and api_format != config.API_FORMAT_CLAUDE:
                    QMessageBox.warning(self, "提示", "当前模型列表为空，请先点击「获取模型」按钮获取最新的模型列表")
                    return

        # 禁用测试按钮，显示测试中状态
        self.test_connection_button.setEnabled(False)
        self.test_connection_button.setText("⏳ 测试中...")

        # 输出测试开始日志到主界面
        if self.parent_window and hasattr(self.parent_window, 'log_message'):
            self.parent_window.log_message("开始测试LLM连接...")

        # 创建工作线程 - 传递API格式参数
        self.test_thread = QThread()
        self.test_worker = LlmTestWorker(api_key, api_base_url, model_name, temperature, api_format)
        self.test_worker.moveToThread(self.test_thread)

        # 连接信号
        self.test_thread.started.connect(self.test_worker.run)
        self.test_worker.finished.connect(self._on_connection_tested)

        # 连接日志信号到主界面
        if self.parent_window and hasattr(self.parent_window, 'log_message'):
            self.test_worker.log_message.connect(self.parent_window.log_message)

        self.test_worker.finished.connect(self.test_thread.quit)
        self.test_worker.finished.connect(self.test_worker.deleteLater)
        self.test_thread.finished.connect(self.test_thread.deleteLater)

        self.test_thread.start()

        # 设置30秒超时定时器
        self.test_timeout_timer = QTimer()
        self.test_timeout_timer.setSingleShot(True)
        self.test_timeout_timer.timeout.connect(self._on_test_timeout)
        self.test_timeout_timer.start(30000)  # 30秒

    def _on_test_timeout(self):
        """处理测试连接超时"""
        if self.test_thread and self.test_thread.isRunning():
            self.test_thread.quit()
            self.test_thread.wait(3000)  # 等待3秒让线程结束
            self.test_worker = None
            self.test_thread = None

            # 恢复测试按钮状态
            self.test_connection_button.setEnabled(True)
            self.test_connection_button.setText("测试当前配置连接")

            QMessageBox.warning(self, "超时", "测试连接超时，可能是网络连接问题或API服务器响应缓慢。请检查网络连接后重试。")

            # 输出超时日志到主界面
            if self.parent_window and hasattr(self.parent_window, 'log_message'):
                self.parent_window.log_message("⚠️ LLM连接测试超时")

    def _on_connection_tested(self, success: bool, message: str):
        """处理连接测试结果"""
        try:
            # 停止超时定时器
            if hasattr(self, 'test_timeout_timer'):
                self.test_timeout_timer.stop()
                self.test_timeout_timer.deleteLater()
                self.test_timeout_timer = None
            # 恢复按钮状态
            self.test_connection_button.setEnabled(True)
            self.test_connection_button.setText("测试当前配置连接")

            # 输出测试结果日志到主界面
            if self.parent_window and hasattr(self.parent_window, 'log_message'):
                if success:
                    self.parent_window.log_message(f"✅ LLM连接测试成功: {message}")
                else:
                    self.parent_window.log_message(f"❌ LLM连接测试失败: {message}")

            # 显示弹窗
            if success:
                QMessageBox.information(self, "连接成功", message)
            else:
                QMessageBox.warning(self, "连接失败", message)
        finally:
            # 清理线程引用
            self.test_worker = None
            self.test_thread = None

    def accept(self):
        """保存并关闭对话框"""
        # 保存当前正在编辑的配置
        if not self._save_current_profile():
            QMessageBox.warning(self, "保存失败", "无法保存当前配置，请检查配置信息是否完整")
            return

        # 发出信号保存所有配置到文件
        self.settings_applied.emit(self.config)

        # 输出日志到主界面
        if self.parent_window and hasattr(self.parent_window, 'log_message'):
            self.parent_window.log_message("✅ LLM配置已保存")

        # 关闭对话框
        super().accept()

    def reject(self):
        """关闭对话框"""
        self._cleanup_threads()
        super().reject()

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 清理线程
        self._cleanup_threads()
        super().closeEvent(event)

    def _sync_default_profile_to_main_window(self):
        """同步默认配置到主窗口（仅在保存后调用）"""
        if not self.parent_window or not hasattr(self.parent_window, 'api_key_entry'):
            return

        # 查找默认配置
        default_profile = None
        for profile in self.profiles:
            if profile.get("is_default", False):
                default_profile = profile
                break

        if not default_profile:
            return

        # 同步默认配置的API Key到主界面
        default_api_key = default_profile.get("api_key", "")
        self.parent_window.api_key_entry.setText(default_api_key)

        # 更新主界面的复选框状态
        has_saved_key = bool(default_api_key)
        if hasattr(self.parent_window, 'remember_api_key_checkbox'):
            self.parent_window.remember_api_key_checkbox.setChecked(has_saved_key)

        # 记录日志
        if hasattr(self.parent_window, 'log_message'):
            self.parent_window.log_message(f"已同步默认配置到主界面")

    def _cleanup_threads(self):
        """清理工作线程"""
        try:
            # 清理测试连接线程
            if self.test_thread and self.test_thread.isRunning():
                self.test_thread.quit()
                self.test_thread.wait(3000)  # 等待最多3秒
            self.test_thread = None
            self.test_worker = None

            # 清理获取模型列表线程
            if self.fetch_thread and self.fetch_thread.isRunning():
                self.fetch_thread.quit()
                self.fetch_thread.wait(3000)  # 等待最多3秒
            self.fetch_thread = None
            self.fetch_worker = None

            # 清理超时定时器
            if hasattr(self, 'test_timeout_timer') and self.test_timeout_timer:
                self.test_timeout_timer.stop()
                self.test_timeout_timer.deleteLater()
                self.test_timeout_timer = None

            if hasattr(self, 'fetch_timeout_timer') and self.fetch_timeout_timer:
                self.fetch_timeout_timer.stop()
                self.fetch_timeout_timer.deleteLater()
                self.fetch_timeout_timer = None
        except Exception:
            # 忽略清理过程中的异常
            pass

    def refresh_available_models(self, api_key: str, api_base_url: str) -> tuple[bool, list]:
        """
        公共方法：刷新当前配置的可用模型列表

        Args:
            api_key: API密钥
            api_base_url: API基础URL

        Returns:
            tuple[bool, list]: (是否成功刷新模型列表, 模型列表)
        """
        try:
            # 获取模型列表 - 使用ModelFetchWorker
            worker = ModelFetchWorker(api_base_url, api_key, "unknown")  # provider参数暂时使用"unknown"
            models, message = worker._fetch_models()

            if models:
                # 更新当前配置中的模型列表
                if self.parent_window and hasattr(self.parent_window, 'config'):
                    current_profile_id = self.parent_window.config.get(config.CURRENT_PROFILE_ID_KEY)
                    if current_profile_id:
                        llm_profiles_config = self.parent_window.config.get(config.LLM_PROFILES_KEY, {})
                        profiles = llm_profiles_config.get("profiles", [])
                        for profile in profiles:
                            if profile.get('id') == current_profile_id:
                                profile["available_models"] = models
                                break

                # 更新本对话框profiles中的模型列表（用于自动刷新功能）
                if hasattr(self, 'profiles') and self.profiles:
                    current_profile_id = self.config.get(config.CURRENT_PROFILE_ID_KEY)
                    if current_profile_id:
                        for profile in self.profiles:
                            if profile.get('id') == current_profile_id:
                                profile["available_models"] = models
                                break

                # 更新UI中的模型下拉框
                if hasattr(self, 'model_name_combo'):
                    current_model = self.model_name_combo.currentText()
                    self.model_name_combo.clear()
                    for model in models:
                        self.model_name_combo.addItem(model)

                    # 设置当前选择的模型
                    if current_model and current_model in models:
                        self.model_name_combo.setCurrentText(current_model)
                    elif models:
                        self.model_name_combo.setCurrentIndex(0)

                return True, models
            return False, []
        except Exception:
            # 静默失败，不影响程序启动
            return False, []

    def mousePressEvent(self, event):
        """鼠标按下事件，用于窗口拖拽功能"""
        if event.button() == Qt.MouseButton.LeftButton:
            if event.position().y() < 40:
                self.drag_pos = event.globalPosition().toPoint()
                self.is_dragging_dialog = True
                event.accept()
            else:
                self.is_dragging_dialog = False
                super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件，实现窗口拖拽"""
        if hasattr(self, 'is_dragging_dialog') and self.is_dragging_dialog and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = event.globalPosition().toPoint()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件，结束窗口拖拽"""
        if hasattr(self, 'is_dragging_dialog'):
            self.is_dragging_dialog = False
        super().mouseReleaseEvent(event)