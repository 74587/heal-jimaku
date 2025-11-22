import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QSpacerItem, QSizePolicy, QWidget, QComboBox, QCheckBox, QFileDialog,
    QMessageBox, QGroupBox, QSpinBox, QTextEdit, QButtonGroup, QRadioButton,
    QFormLayout, QScrollArea, QFrame, QStackedWidget, QGridLayout, QListWidget,
    QListWidgetItem, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint, QSize
from PyQt6.QtGui import QFont, QColor, QIcon, QPixmap

from ui.custom_widgets import CustomLabel, TransparentWidget, StrokeCheckBoxWidget
from utils.file_utils import resource_path
from config import (
    DEFAULT_CLOUD_TRANSCRIPTION_PROVIDER,
    DEFAULT_ELEVENLABS_API_KEY,
    DEFAULT_ELEVENLABS_API_REMEMBER_KEY,
    DEFAULT_ELEVENLABS_API_LANGUAGE,
    DEFAULT_ELEVENLABS_API_NUM_SPEAKERS,
    DEFAULT_ELEVENLABS_API_ENABLE_DIARIZATION,
    DEFAULT_ELEVENLABS_API_TAG_AUDIO_EVENTS,
    DEFAULT_SONIOX_API_KEY,
    DEFAULT_SONIOX_API_REMEMBER_KEY,
    DEFAULT_SONIOX_LANGUAGE_HINTS,
    DEFAULT_SONIOX_ENABLE_SPEAKER_DIARIZATION,
    DEFAULT_SONIOX_ENABLE_LANGUAGE_IDENTIFICATION,
    DEFAULT_SONIOX_CONTEXT_TERMS,
    DEFAULT_SONIOX_CONTEXT_TEXT,
    DEFAULT_SONIOX_CONTEXT_GENERAL,
    CLOUD_PROVIDER_ELEVENLABS_WEB,
    CLOUD_PROVIDER_ELEVENLABS_API,
    CLOUD_PROVIDER_SONIOX_API,
    SUPPORTED_LANGUAGES,
    SONIOX_SUPPORTED_LANGUAGES
)
from core.elevenlabs_api import ElevenLabsSTTClient
from core.soniox_api import SonioxClient


class CloudTranscriptionDialog(QDialog):
    """云端转录设置对话框 - 最终UI优化版"""

    settings_confirmed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("云端转录设置")
        self.setModal(True)
        self.current_settings = current_settings = getattr(parent, 'cloud_transcription_settings', {})
        self.selected_audio_file_path = ""
        self.selected_audio_files = []

        # API客户端实例
        self.elevenlabs_client = None
        self.soniox_client = None

        # === 窗口尺寸配置 ===
        self.DIALOG_SIZES = {
            0: (900, 650),  # Web版
            1: (900, 700),  # API版
            2: (980, 850)   # Soniox版
        }

        # 窗口属性
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # 主容器
        container = QWidget(self)
        container.setObjectName("cloudTranscriptionDialogContainer")
        container.setStyleSheet("""
            QWidget#cloudTranscriptionDialogContainer {
                background-color: rgba(60, 60, 80, 240);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.15);
            }
        """)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)

        # 内容布局
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(30, 25, 30, 25)
        main_layout.setSpacing(15)

        # 颜色定义
        self.param_label_main_color = QColor(87, 128, 183)
        self.param_label_stroke_color = QColor(242, 234, 218)

        # 构建UI
        self._create_title_bar(main_layout)
        self._create_file_selection_area(main_layout)
        self._create_provider_selection_area(main_layout)
        self._create_dynamic_config_area(main_layout)
        
        # 弹性空间
        main_layout.addStretch(1)
        
        self._create_action_buttons(main_layout)

        # 初始化逻辑
        self._initialize_settings()
        
        # 启动时初始化尺寸策略
        QTimer.singleShot(0, lambda: self._on_provider_changed(self.provider_combo.currentIndex()))

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(10, self._center_on_parent)

    def _center_on_parent(self):
        if self.parent_window:
            geo = self.parent_window.geometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)
        else:
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                x = (geo.width() - self.width()) // 2
                y = (geo.height() - self.height()) // 2
                self.move(x, y)

    def _update_dialog_size(self):
        """强制应用预设的尺寸"""
        idx = self.provider_combo.currentIndex()
        width, height = self.DIALOG_SIZES.get(idx, (900, 500))
        
        self.setMinimumSize(0, 0) 
        self.resize(width, height)
        self.setMinimumSize(800, 350)
        self._center_on_parent()

    def _on_provider_changed(self, index):
        """服务商切换回调"""
        self.config_stack.setCurrentIndex(index)
        
        # 调整 StackWidget 页面策略
        for i in range(self.config_stack.count()):
            page = self.config_stack.widget(i)
            if i == index:
                page.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
                page.show()
            else:
                page.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
                page.hide()

        self._update_dialog_size()

    def _create_title_bar(self, layout):
        title_bar_layout = QHBoxLayout()
        
        title_label = CustomLabel("云端转录设置")
        title_label.setCustomColors(main_color=self.param_label_main_color, stroke_color=self.param_label_stroke_color)
        title_font = QFont('楷体', 22, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        close_button = QPushButton()
        close_button.setFixedSize(32, 32)
        close_button.setObjectName("dialogCloseButton")
        close_button.setToolTip("关闭")
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.clicked.connect(self.reject)
        
        icon_path = resource_path("dialog_close_normal.png")
        if icon_path and os.path.exists(icon_path):
             close_button.setIcon(QIcon(icon_path))
             close_button.setIconSize(QSize(20, 20))
        else:
            close_button.setText("×")
            
        close_button.setStyleSheet("""
            QPushButton#dialogCloseButton {
                background-color: rgba(255, 99, 71, 160); 
                color: white;
                border: none; 
                border-radius: 16px;
                font-weight: bold; 
                font-family: Arial;
                font-size: 16pt;
                padding: 0px;
            }
            QPushButton#dialogCloseButton:hover {
                background-color: rgba(255, 99, 71, 220);
            }
        """)

        title_bar_layout.addStretch()
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(close_button)
        layout.addLayout(title_bar_layout)

    def _create_file_selection_area(self, layout):
        file_group = QGroupBox("音频文件")
        file_group.setStyleSheet(self._get_group_style())
        
        file_layout = QVBoxLayout(file_group)
        file_layout.setSpacing(8)
        file_layout.setContentsMargins(15, 25, 15, 10)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)

        self.file_path_entry = QLineEdit()
        self.file_path_entry.setPlaceholderText("请点击浏览按钮选择音频文件...") 
        self.file_path_entry.setReadOnly(True)
        self.file_path_entry.setStyleSheet(self._get_input_style())
        self.file_path_entry.setMinimumHeight(38)

        browse_btn = QPushButton("浏览...")
        browse_btn.setFixedSize(90, 38)
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.setStyleSheet(self._get_btn_style())
        browse_btn.clicked.connect(self._select_audio_file)

        input_layout.addWidget(self.file_path_entry)
        input_layout.addWidget(browse_btn)
        file_layout.addLayout(input_layout)

        hint_label = QLabel("📁 支持批量选择多个音频文件进行处理")
        hint_label.setStyleSheet("color: rgba(242, 234, 218, 0.9); font-size: 13px; font-weight: bold; padding-left: 2px;")
        file_layout.addWidget(hint_label)

        layout.addWidget(file_group)

    def _create_provider_selection_area(self, layout):
        group = QGroupBox("服务商")
        group.setStyleSheet(self._get_group_style())
        
        group_layout = QHBoxLayout(group)
        group_layout.setContentsMargins(15, 25, 15, 15)
        group_layout.setSpacing(15)

        label = CustomLabel("转录服务商:")
        label.setFont(QFont('楷体', 16, QFont.Weight.Bold))
        label.setCustomColors(self.param_label_main_color, self.param_label_stroke_color)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "ElevenLabs (Web/Free) - 免费在线版",
            "ElevenLabs (API/Paid) - 官方API版",
            "Soniox (API/Paid) - 专业会议转录"
        ])
        self.provider_combo.setMinimumHeight(38)
        self.provider_combo.setStyleSheet(self._get_combo_style())
        
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)

        group_layout.addWidget(label)
        group_layout.addWidget(self.provider_combo, 1)
        layout.addWidget(group)

    def _create_dynamic_config_area(self, layout):
        config_group = QGroupBox("转录参数")
        config_group.setStyleSheet(self._get_group_style())
        
        group_layout = QVBoxLayout(config_group)
        group_layout.setContentsMargins(5, 20, 5, 5)

        self.config_stack = QStackedWidget()
        self.config_stack.setStyleSheet("background: transparent;")
        self.config_stack.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        
        self._create_elevenlabs_web_config()
        self._create_elevenlabs_api_config()
        self._create_soniox_api_config()

        group_layout.addWidget(self.config_stack)
        layout.addWidget(config_group)

    def _create_elevenlabs_web_config(self):
        """Page 0: ElevenLabs Web"""
        page = QWidget()
        layout = QGridLayout(page)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(15)
        label_font = QFont('楷体', 15, QFont.Weight.Bold)

        # Row 0: 语言
        lbl_lang = CustomLabel("目标语言:")
        lbl_lang.setFont(label_font)
        lbl_lang.setCustomColors(self.param_label_main_color, self.param_label_stroke_color)
        
        self.el_web_language_combo = QComboBox()
        self.el_web_language_combo.addItems([n for c, n in SUPPORTED_LANGUAGES])
        self.el_web_language_combo.setStyleSheet(self._get_combo_style())
        self.el_web_language_combo.setMinimumHeight(38)

        layout.addWidget(lbl_lang, 0, 0)
        layout.addWidget(self.el_web_language_combo, 0, 1)

        # Row 1: 人数
        lbl_spk = CustomLabel("说话人数:")
        lbl_spk.setFont(label_font)
        lbl_spk.setCustomColors(self.param_label_main_color, self.param_label_stroke_color)
        
        self.el_web_speakers_spin = QSpinBox()
        self.el_web_speakers_spin.setRange(0, 10)
        self.el_web_speakers_spin.setValue(0)
        self.el_web_speakers_spin.setSuffix(" 人 (0=自动)")
        self.el_web_speakers_spin.setToolTip("0 表示自动检测说话人数")
        self.el_web_speakers_spin.setStyleSheet(self._get_input_style())
        self.el_web_speakers_spin.setMinimumHeight(38)

        layout.addWidget(lbl_spk, 1, 0)
        layout.addWidget(self.el_web_speakers_spin, 1, 1)

        # Row 2: 开关 - 放在第1列，与上方控件对齐
        self.el_web_audio_events_check = StrokeCheckBoxWidget("标记音频事件 (如 [笑声])")
        self.el_web_audio_events_check.setChecked(True)
        layout.addWidget(self.el_web_audio_events_check, 2, 1, 1, 2, Qt.AlignmentFlag.AlignLeft)

        layout.setColumnStretch(1, 1)
        layout.setRowStretch(3, 1)

        self.config_stack.addWidget(page)

    def _create_elevenlabs_api_config(self):
        """Page 1: ElevenLabs API"""
        page = QWidget()
        layout = QGridLayout(page)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(15)
        label_font = QFont('楷体', 15, QFont.Weight.Bold)

        # Row 0: API Key
        lbl_key = CustomLabel("API Key:")
        lbl_key.setFont(label_font)
        lbl_key.setCustomColors(self.param_label_main_color, self.param_label_stroke_color)
        
        key_box = QHBoxLayout()
        key_box.setSpacing(10)
        self.el_api_key_edit = QLineEdit()
        self.el_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.el_api_key_edit.setStyleSheet(self._get_input_style())
        self.el_api_key_edit.setMinimumHeight(38)
        
        self.el_api_key_toggle = QPushButton()
        self.el_api_key_toggle.setFixedSize(38, 38)
        self._setup_eye_button(self.el_api_key_toggle)
        self.el_api_key_toggle.clicked.connect(lambda: self._toggle_visibility(self.el_api_key_edit, self.el_api_key_toggle))
        
        key_box.addWidget(self.el_api_key_edit)
        key_box.addWidget(self.el_api_key_toggle)

        layout.addWidget(lbl_key, 0, 0)
        layout.addLayout(key_box, 0, 1, 1, 3)

        # Row 1: 记住 & 测试
        self.el_api_remember_check = StrokeCheckBoxWidget("记住API密钥")
        self.el_api_test_button = QPushButton("测试连接")
        self.el_api_test_button.setFixedSize(100, 34)
        self.el_api_test_button.setStyleSheet(self._get_btn_style())
        self.el_api_test_button.clicked.connect(self._test_elevenlabs_api_connection)
        
        layout.addWidget(self.el_api_remember_check, 1, 1, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.el_api_test_button, 1, 3, Qt.AlignmentFlag.AlignRight)

        # Row 2: 语言 & 人数
        lbl_lang = CustomLabel("目标语言:")
        lbl_lang.setFont(label_font)
        lbl_lang.setCustomColors(self.param_label_main_color, self.param_label_stroke_color)
        
        self.el_api_language_combo = QComboBox()
        self.el_api_language_combo.addItems([n for c, n in SUPPORTED_LANGUAGES])
        self.el_api_language_combo.setStyleSheet(self._get_combo_style())
        self.el_api_language_combo.setMinimumHeight(38)

        lbl_spk = CustomLabel("说话人数:")
        lbl_spk.setFont(label_font)
        lbl_spk.setCustomColors(self.param_label_main_color, self.param_label_stroke_color)

        self.el_api_speakers_spin = QSpinBox()
        self.el_api_speakers_spin.setRange(0, 32)
        self.el_api_speakers_spin.setValue(0)
        self.el_api_speakers_spin.setSuffix(" 人 (0=自动)")
        self.el_api_speakers_spin.setToolTip("0 表示自动检测说话人数")
        self.el_api_speakers_spin.setStyleSheet(self._get_input_style())
        self.el_api_speakers_spin.setMinimumHeight(38)

        layout.addWidget(lbl_lang, 2, 0)
        layout.addWidget(self.el_api_language_combo, 2, 1)
        layout.addWidget(lbl_spk, 2, 2)
        layout.addWidget(self.el_api_speakers_spin, 2, 3)

        # Row 3: 启用说话人分离 (单独一行)
        self.el_api_diarization_check = StrokeCheckBoxWidget("启用说话人分离")
        layout.addWidget(self.el_api_diarization_check, 3, 1, 1, 3, Qt.AlignmentFlag.AlignLeft)

        # Row 4: 标记音频事件 (单独一行)
        self.el_api_audio_events_check = StrokeCheckBoxWidget("标记音频事件")
        layout.addWidget(self.el_api_audio_events_check, 4, 1, 1, 3, Qt.AlignmentFlag.AlignLeft)

        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)
        self.config_stack.addWidget(page)

    def _create_soniox_api_config(self):
        """Page 2: Soniox API"""
        page = QWidget()
        main_layout = QGridLayout(page)
        main_layout.setContentsMargins(10, 0, 10, 0)
        main_layout.setSpacing(20)
        label_font = QFont('楷体', 15, QFont.Weight.Bold)

        # Row 0: API Key (紧凑布局，无左侧空白)
        lbl_key = CustomLabel("API Key:")
        lbl_key.setFont(label_font)
        lbl_key.setCustomColors(main_color=self.param_label_main_color, stroke_color=self.param_label_stroke_color)
        # 强制标签宽度以确保对齐，或者让HBox处理
        
        key_box = QHBoxLayout()
        key_box.setSpacing(10)
        self.soniox_api_key_edit = QLineEdit()
        self.soniox_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.soniox_api_key_edit.setStyleSheet(self._get_input_style())
        self.soniox_api_key_edit.setMinimumHeight(38)

        self.soniox_api_key_toggle = QPushButton()
        self.soniox_api_key_toggle.setFixedSize(38, 38)
        self._setup_eye_button(self.soniox_api_key_toggle)
        self.soniox_api_key_toggle.clicked.connect(lambda: self._toggle_visibility(self.soniox_api_key_edit, self.soniox_api_key_toggle))
        
        btn_test = QPushButton("测试连接")
        btn_test.setFixedSize(100, 34)
        btn_test.setStyleSheet(self._get_btn_style())
        btn_test.clicked.connect(self._test_soniox_api_connection)

        # 关键修改：直接将Label加入HBox，不占用Grid的第0列
        # 或者让HBox占据Grid的一整行
        # 这里选择将Label放在 Grid(0,0)，其他放在 Grid(0,1-3)
        
        main_layout.addWidget(lbl_key, 0, 0)
        
        # 嵌套布局以确保紧凑
        input_btn_layout = QHBoxLayout()
        input_btn_layout.setSpacing(10)
        input_btn_layout.setContentsMargins(0,0,0,0)
        input_btn_layout.addWidget(self.soniox_api_key_edit)
        input_btn_layout.addWidget(self.soniox_api_key_toggle)
        input_btn_layout.addWidget(btn_test)
        
        main_layout.addLayout(input_btn_layout, 0, 1, 1, 3) # 占据剩余列
        
        self.soniox_api_remember_check = StrokeCheckBoxWidget("记住API密钥")
        main_layout.addWidget(self.soniox_api_remember_check, 1, 1, 1, 3, Qt.AlignmentFlag.AlignLeft)

        # 左栏 - 基础设置
        left_group = QGroupBox("基础设置")
        left_group.setStyleSheet(self._get_sub_group_style())
        left_layout = QVBoxLayout(left_group)
        left_layout.setSpacing(12)
        left_layout.setContentsMargins(15, 25, 15, 15)

        lbl_hints = CustomLabel("语言提示 (多选):")
        lbl_hints.setFont(label_font)
        lbl_hints.setCustomColors(self.param_label_main_color, self.param_label_stroke_color)
        
        self.soniox_language_list = QListWidget()
        self.soniox_language_list.setStyleSheet(self._get_list_style())
        for code, name in SONIOX_SUPPORTED_LANGUAGES[:15]:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, code)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if code in ["ja", "zh", "en"] else Qt.CheckState.Unchecked)
            self.soniox_language_list.addItem(item)
        
        left_layout.addWidget(lbl_hints)
        left_layout.addWidget(self.soniox_language_list)
        
        self.soniox_diarization_check = StrokeCheckBoxWidget("启用说话人分离")
        left_layout.addWidget(self.soniox_diarization_check, 0, Qt.AlignmentFlag.AlignLeft)
        
        self.soniox_language_identification_check = StrokeCheckBoxWidget("启用语言识别")
        left_layout.addWidget(self.soniox_language_identification_check, 0, Qt.AlignmentFlag.AlignLeft)

        # 右栏 - Context 优化
        right_group = QGroupBox("Context 优化")
        right_group.setStyleSheet(self._get_sub_group_style())
        right_layout = QVBoxLayout(right_group)
        right_layout.setSpacing(12)
        right_layout.setContentsMargins(15, 25, 15, 15)

        lbl_terms = CustomLabel("专有名词:")
        lbl_terms.setFont(label_font)
        lbl_terms.setCustomColors(self.param_label_main_color, self.param_label_stroke_color)
        self.soniox_terms_edit = QTextEdit()
        self.soniox_terms_edit.setPlaceholderText("角色名\n地名\n特殊术语...")
        self.soniox_terms_edit.setStyleSheet(self._get_input_style())
        
        lbl_ctx = CustomLabel("剧情简介:")
        lbl_ctx.setFont(label_font)
        lbl_ctx.setCustomColors(self.param_label_main_color, self.param_label_stroke_color)
        self.soniox_context_edit = QTextEdit()
        self.soniox_context_edit.setPlaceholderText("输入简短的背景描述，帮助AI理解上下文...")
        self.soniox_context_edit.setStyleSheet(self._get_input_style())

        right_layout.addWidget(lbl_terms)
        right_layout.addWidget(self.soniox_terms_edit, 1)
        right_layout.addWidget(lbl_ctx)
        right_layout.addWidget(self.soniox_context_edit, 2)

        main_layout.addWidget(left_group, 2, 0, 1, 2)
        main_layout.addWidget(right_group, 2, 2, 1, 2)

        for i in range(4):
            main_layout.setColumnStretch(i, 1)

        self.config_stack.addWidget(page)

    def _create_action_buttons(self, layout):
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 5, 0, 10)
        button_layout.setSpacing(20)
        
        button_layout.addStretch()

        cancel_button = QPushButton("取消")
        cancel_button.setFixedSize(120, 45)
        cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_button.setStyleSheet(self._get_cancel_btn_style())
        cancel_button.clicked.connect(self.reject)
        
        confirm_button = QPushButton("确定") # 修改文字为确定
        confirm_button.setFixedSize(140, 45)
        confirm_button.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_button.setStyleSheet(self._get_ok_btn_style())
        confirm_button.clicked.connect(self._confirm_settings)
        
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(confirm_button)
        button_layout.addStretch()

        layout.addWidget(button_container)

    def _setup_eye_button(self, button):
        button.setStyleSheet(self._get_icon_btn_style())
        icon_path = resource_path("eye-Invisible.png")
        if icon_path and os.path.exists(icon_path):
            button.setIcon(QIcon(icon_path))
            button.setIconSize(QSize(22, 22))
        else:
            button.setText("🙈")

    def _toggle_visibility(self, line_edit, button):
        if line_edit.echoMode() == QLineEdit.EchoMode.Password:
            line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            icon = resource_path("eye-Visible.png")
        else:
            line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            icon = resource_path("eye-Invisible.png")
        
        if icon and os.path.exists(icon):
            button.setIcon(QIcon(icon))
        else:
            button.setText("👁" if line_edit.echoMode() == QLineEdit.EchoMode.Password else "🙈")

    # --- Styles ---
    def _get_group_style(self):
        return "QGroupBox { color: #F2EADA; font: bold 16px '楷体'; border: 1px solid rgba(87, 128, 183, 0.4); border-radius: 8px; margin-top: 12px; padding-top: 15px; background-color: rgba(255, 255, 255, 8); } QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 5px; color: #B34A4A; }"
    
    def _get_sub_group_style(self):
        return "QGroupBox { color: #F2EADA; font: bold 14px '楷体'; border: 2px solid rgba(87, 128, 183, 0.6); border-radius: 6px; margin-top: 10px; background-color: transparent; } QGroupBox::title { subcontrol-origin: margin; left: 10px; color: #FF6B6B; }"
    
    def _get_input_style(self):
        # 统一所有输入框样式：背景色、字体颜色、边框颜色、字体、内边距
        return """
            QLineEdit, QSpinBox, QTextEdit { 
                background-color: rgba(255, 255, 255, 60); 
                color: #FFFFFF; 
                border: 1px solid rgba(120, 195, 225, 140); 
                border-radius: 6px; 
                padding: 5px 10px; 
                font-size: 14px; 
                font-family: 'Microsoft YaHei'; 
            } 
            QLineEdit:focus, QSpinBox:focus, QTextEdit:focus {
                border: 2px solid rgba(120, 195, 225, 220);
                background-color: rgba(255, 255, 255, 80);
            }
            /* 确保 QTextEdit 内部没有额外边框 */
            QTextEdit { outline: none; }
        """
    
    def _get_combo_style(self):
        dropdown_arrow_path_str = resource_path('dropdown_arrow.png')
        qss_dropdown_arrow = ""
        if dropdown_arrow_path_str and os.path.exists(dropdown_arrow_path_str):
             qss_dropdown_arrow = f"url('{dropdown_arrow_path_str.replace(os.sep, '/')}')"

        # 与 _get_input_style 保持高度一致
        return f"""
            QComboBox {{
                background-color: rgba(255, 255, 255, 60);
                color: #FFFFFF;
                border: 1px solid rgba(120, 195, 225, 140);
                border-radius: 6px;
                padding: 5px 8px;
                font-family: 'Microsoft YaHei';
                font-size: 14px;
                min-height: 1.9em;
            }}
            QComboBox:hover {{
                background-color: rgba(255, 255, 255, 80);
                border-color: rgba(120, 195, 225, 180);
            }}
            QComboBox:focus {{
                background-color: rgba(255, 255, 255, 80);
                border: 2px solid rgba(120, 195, 225, 220);
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 30px;
                border-left: 1px solid rgba(120, 195, 225, 140);
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background-color: rgba(120, 195, 225, 120);
            }}
            QComboBox::down-arrow {{
                image: {qss_dropdown_arrow if qss_dropdown_arrow else "none"};
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: rgba(70, 70, 90, 240);
                color: #EAEAEA;
                border: 1px solid rgba(135, 206, 235, 150);
                border-radius: 6px;
                padding: 4px;
                outline: 0px;
                selection-background-color: rgba(120, 195, 225, 200);
                font-family: 'Microsoft YaHei';
                font-size: 14px;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 10px;
                min-height: 2.2em;
                border-radius: 3px;
                background-color: transparent;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(120, 195, 225, 200), stop:1 rgba(85, 160, 190, 180));
                color: white;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(120, 195, 225, 120), stop:1 rgba(85, 160, 190, 100));
            }}
            QScrollBar:vertical {{
                border: none;
                background: rgba(0, 0, 0, 30);
                width: 10px;
                margin: 0px 0px 0px 0px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255, 255, 255, 80);
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(255, 255, 255, 120);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                subcontrol-origin: margin;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """

    def _get_btn_style(self):
        return """
            QPushButton {
                background-color: rgba(100, 149, 237, 170);
                color: white;
                border: 1px solid rgba(135, 206, 235, 100);
                border-radius: 6px;
                font-family: '楷体';
                font-weight: bold;
                font-size: 13pt;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: rgba(120, 169, 247, 200); }
            QPushButton:pressed { background-color: rgba(80, 129, 217, 200); }
        """
    
    def _get_cancel_btn_style(self):
        return "QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(220, 53, 69, 180), stop:1 rgba(180, 40, 50, 200)); color: white; border: 1px solid rgba(220, 53, 69, 150); border-radius: 8px; font-family: '楷体'; font-size: 15pt; font-weight: bold; } QPushButton:hover { background: rgba(220, 53, 69, 220); }"
    
    def _get_ok_btn_style(self):
        return "QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(40, 167, 69, 180), stop:1 rgba(30, 130, 55, 200)); color: white; border: 1px solid rgba(40, 167, 69, 150); border-radius: 8px; font-family: '楷体'; font-size: 15pt; font-weight: bold; } QPushButton:hover { background: rgba(40, 167, 69, 220); }"
    
    def _get_icon_btn_style(self):
        return "QPushButton { background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 5px; color: #DDD; font-size: 16px; } QPushButton:hover { background: rgba(255, 255, 255, 0.2); }"
    
    def _get_list_style(self):
        return "QListWidget { background-color: rgba(255, 255, 255, 0.15); border: 1px solid rgba(87, 128, 183, 0.4); border-radius: 5px; color: #F2EADA; font-size: 13px; } QListWidget::item { padding: 4px; } QListWidget::item:hover { background: rgba(255, 255, 255, 0.2); }"

    # --- 逻辑功能 ---
    def _initialize_settings(self):
        provider = self.current_settings.get('provider', DEFAULT_CLOUD_TRANSCRIPTION_PROVIDER)
        idx = 0
        if provider == CLOUD_PROVIDER_ELEVENLABS_API: idx = 1
        elif provider == CLOUD_PROVIDER_SONIOX_API: idx = 2
        self.provider_combo.setCurrentIndex(idx)
        self._update_file_display()

    def update_file_display(self):
        self._update_file_display()

    def _update_file_display(self):
        if self.selected_audio_file_path:
            self.file_path_entry.setText(os.path.basename(self.selected_audio_file_path))
        elif self.selected_audio_files:
            self.file_path_entry.setText(f"已选择 {len(self.selected_audio_files)} 个音频文件")
        else:
            self.file_path_entry.clear()

    def _select_audio_file(self):
        curr_dir = os.path.dirname(self.selected_audio_file_path) if self.selected_audio_file_path else os.path.expanduser("~")
        files, _ = QFileDialog.getOpenFileNames(self, "选择音频", curr_dir, "音频文件 (*.mp3 *.wav *.flac *.m4a *.ogg *.aac);;所有文件 (*)")
        if files:
            if len(files) == 1:
                self.selected_audio_file_path = files[0]
                self.selected_audio_files = []
            else:
                self.selected_audio_file_path = ""
                self.selected_audio_files = files
            self._update_file_display()

    def _confirm_settings(self):
        if not self.selected_audio_file_path and not self.selected_audio_files:
            QMessageBox.warning(self, "警告", "请先选择音频文件")
            return
            
        idx = self.provider_combo.currentIndex()
        providers = [CLOUD_PROVIDER_ELEVENLABS_WEB, CLOUD_PROVIDER_ELEVENLABS_API, CLOUD_PROVIDER_SONIOX_API]
        provider = providers[idx]
        
        settings = {
            'audio_file_path': self.selected_audio_file_path,
            'audio_files': self.selected_audio_files,
            'provider': provider
        }

        if provider == CLOUD_PROVIDER_ELEVENLABS_WEB:
            settings.update({
                'language': SUPPORTED_LANGUAGES[self.el_web_language_combo.currentIndex()][0],
                'num_speakers': self.el_web_speakers_spin.value(),
                'tag_audio_events': self.el_web_audio_events_check.isChecked()
            })
        elif provider == CLOUD_PROVIDER_ELEVENLABS_API:
            key = self.el_api_key_edit.text().strip()
            if not key: return QMessageBox.warning(self, "警告", "请输入API Key")
            settings.update({
                'api_key': key,
                'elevenlabs_api_remember_key': self.el_api_remember_check.isChecked(),
                'language': SUPPORTED_LANGUAGES[self.el_api_language_combo.currentIndex()][0],
                'num_speakers': self.el_api_speakers_spin.value(),
                'enable_diarization': self.el_api_diarization_check.isChecked(),
                'tag_audio_events': self.el_api_audio_events_check.isChecked()
            })
        elif provider == CLOUD_PROVIDER_SONIOX_API:
            key = self.soniox_api_key_edit.text().strip()
            if not key: return QMessageBox.warning(self, "警告", "请输入API Key")
            
            hints = []
            for i in range(self.soniox_language_list.count()):
                item = self.soniox_language_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    hints.append(item.data(Qt.ItemDataRole.UserRole))
            
            settings.update({
                'api_key': key,
                'soniox_api_remember_key': self.soniox_api_remember_check.isChecked(),
                'language_hints': hints,
                'enable_speaker_diarization': self.soniox_diarization_check.isChecked(),
                'enable_language_identification': self.soniox_language_identification_check.isChecked(),
                'context_terms': [t.strip() for t in self.soniox_terms_edit.toPlainText().split('\n') if t.strip()],
                'context_text': self.soniox_context_edit.toPlainText().strip(),
                'context_general': []
            })
            
        self.settings_confirmed.emit(settings)
        self.accept()

    def _test_elevenlabs_api_connection(self):
        key = self.el_api_key_edit.text().strip()
        if not key: return QMessageBox.warning(self, "警告", "请先输入API密钥")
        self.el_api_test_button.setEnabled(False); self.el_api_test_button.setText("测试中...")
        
        def task():
            client = self.elevenlabs_client or ElevenLabsSTTClient()
            ok, msg = client.test_official_api_connection(key)
            QTimer.singleShot(0, lambda: self._show_result(self.el_api_test_button, ok, msg))
        import threading; threading.Thread(target=task, daemon=True).start()

    def _test_soniox_api_connection(self):
        key = self.soniox_api_key_edit.text().strip()
        if not key: return QMessageBox.warning(self, "警告", "请先输入API密钥")
        self.soniox_api_test_button.setEnabled(False); self.soniox_api_test_button.setText("测试中...")
        
        def task():
            client = self.soniox_client or SonioxClient()
            ok, msg = client.test_connection(key)
            QTimer.singleShot(0, lambda: self._show_result(self.soniox_api_test_button, ok, msg))
        import threading; threading.Thread(target=task, daemon=True).start()

    def _show_result(self, btn, ok, msg):
        btn.setEnabled(True); btn.setText("测试连接")
        if ok: QMessageBox.information(self, "成功", msg)
        else: QMessageBox.warning(self, "失败", msg)

    @staticmethod
    def get_transcription_settings(current_settings, parent=None):
        d = CloudTranscriptionDialog(parent)
        if d.exec() == QDialog.DialogCode.Accepted: return d.settings_confirmed
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if event.position().y() < 60:
                self.drag_pos = event.globalPosition().toPoint()
                self.is_dragging_dialog = True
                event.accept()
            else:
                self.is_dragging_dialog = False
                super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if hasattr(self, 'is_dragging_dialog') and self.is_dragging_dialog and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = event.globalPosition().toPoint()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.is_dragging_dialog = False
        super().mouseReleaseEvent(event)