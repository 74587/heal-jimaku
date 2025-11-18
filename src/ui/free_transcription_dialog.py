import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QSpacerItem, QSizePolicy, QWidget, QComboBox,
    QCheckBox, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from ui.custom_widgets import CustomLabel # 确保 CustomLabel 已导入
from utils.file_utils import resource_path
from config import (
    DEFAULT_FREE_TRANSCRIPTION_LANGUAGE,
    DEFAULT_FREE_TRANSCRIPTION_NUM_SPEAKERS,
    DEFAULT_FREE_TRANSCRIPTION_TAG_AUDIO_EVENTS
)


class FreeTranscriptionDialog(QDialog):
    """免费转录设置对话框，提供音频文件选择和转录参数配置功能"""
    settings_confirmed = pyqtSignal(dict)

    def __init__(self, current_settings: dict, parent=None):
        """初始化免费转录设置对话框，创建UI界面和音频文件选择组件"""
        super().__init__(parent)
        self.setWindowTitle("JSON输出参数设置")
        self.setModal(True)
        self.current_settings = current_settings
        self.selected_audio_file_path = current_settings.get('audio_file_path', "")
        self.selected_audio_files = []  # 支持多文件选择

        # 设置无边框窗口和半透明背景
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # 创建容器和背景
        container = QWidget(self)
        container.setObjectName("freeTranscriptionDialogContainer")
        container.setStyleSheet("""
            QWidget#freeTranscriptionDialogContainer {
                background-color: rgba(60, 60, 80, 220);
                border-radius: 10px;
            }
        """)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0,0,0,0)
        dialog_layout.addWidget(container)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(25, 20, 25, 20)
        main_layout.setSpacing(18)

        # 设置参数标签颜色
        self.param_label_main_color = QColor(87, 128, 183)
        self.param_label_stroke_color = QColor(242, 234, 218)

        # 创建标题栏
        title_bar_layout = QHBoxLayout()
        title_label = CustomLabel("JSON输出参数设置")
        title_label.setCustomColors(main_color=self.param_label_main_color, stroke_color=self.param_label_stroke_color)
        title_font = QFont('楷体', 20, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        close_button = QPushButton("×")
        close_button.setFixedSize(30, 30)
        close_button.setObjectName("dialogCloseButton")
        close_button.setToolTip("关闭")
        close_button.clicked.connect(self.reject)

        title_bar_layout.addStretch()
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(close_button)
        main_layout.addLayout(title_bar_layout)

        # 创建音频文件选择组件
        audio_file_layout = QHBoxLayout()
        audio_file_label = CustomLabel("音频文件:")
        audio_file_label.setFont(QFont('楷体', 16, QFont.Weight.Bold))
        audio_file_label.setCustomColors(self.param_label_main_color, self.param_label_stroke_color)

        self.audio_file_path_entry = QLineEdit(self.selected_audio_file_path)
        self.audio_file_path_entry.setPlaceholderText("请选择本地音频文件")
        self.audio_file_path_entry.setObjectName("pathEditDialogFT")
        self.audio_file_path_entry.setReadOnly(True)

        browse_audio_button = QPushButton("浏览...")
        browse_audio_button.setObjectName("dialogBrowseButton")
        browse_audio_button.clicked.connect(self._browse_audio_file)

        audio_file_layout.addWidget(audio_file_label, 2)
        audio_file_layout.addWidget(self.audio_file_path_entry, 5)
        audio_file_layout.addWidget(browse_audio_button, 1)
        main_layout.addLayout(audio_file_layout)

        # 创建语言选择组件
        language_layout = QHBoxLayout()
        language_label = CustomLabel("转录语言:")
        language_label.setFont(QFont('楷体', 16, QFont.Weight.Bold))
        language_label.setCustomColors(self.param_label_main_color, self.param_label_stroke_color)
        self.language_combo = QComboBox()
        self.language_combo.addItems(["自动检测", "日语", "中文", "英文", "韩语"])
        current_lang_api_code = self.current_settings.get('language', DEFAULT_FREE_TRANSCRIPTION_LANGUAGE)
        lang_map_to_display = {"auto": "自动检测", "ja": "日语", "zh": "中文", "en": "英文", "ko": "韩语"}
        display_lang_to_set = lang_map_to_display.get(current_lang_api_code, "自动检测")
        self.language_combo.setCurrentText(display_lang_to_set)
        self.language_combo.setObjectName("dialogComboBoxFT")

        language_layout.addWidget(language_label, 2)
        language_layout.addWidget(self.language_combo, 6)
        main_layout.addLayout(language_layout)

        # 创建说话人数选择组件
        num_speakers_layout = QHBoxLayout()
        num_speakers_label = CustomLabel("说话人数:")
        num_speakers_label.setFont(QFont('楷体', 16, QFont.Weight.Bold))
        num_speakers_label.setCustomColors(self.param_label_main_color, self.param_label_stroke_color)
        self.num_speakers_combo = QComboBox()
        self.num_speakers_combo.addItem("自动检测", 0)
        for i in range(1, 33):
            self.num_speakers_combo.addItem(str(i), i)
        current_num_speakers = self.current_settings.get('num_speakers', DEFAULT_FREE_TRANSCRIPTION_NUM_SPEAKERS)
        num_speaker_index = self.num_speakers_combo.findData(current_num_speakers)
        if num_speaker_index != -1:
            self.num_speakers_combo.setCurrentIndex(num_speaker_index)
        else:
            self.num_speakers_combo.setCurrentText("自动检测")
        self.num_speakers_combo.setObjectName("dialogComboBoxFT")

        num_speakers_layout.addWidget(num_speakers_label, 2)
        num_speakers_layout.addWidget(self.num_speakers_combo, 6)
        main_layout.addLayout(num_speakers_layout)

        # 确保语言和说话人数控件始终可用
        self.language_combo.setEnabled(True)
        self.num_speakers_combo.setEnabled(True)

        # 创建音频事件标记复选框
        checkbox_layout = QHBoxLayout()
        checkbox_layout.addStretch(1)
        self.tag_events_checkbox = QCheckBox("生成非语音声音事件")
        self.tag_events_checkbox.setChecked(self.current_settings.get('tag_audio_events', DEFAULT_FREE_TRANSCRIPTION_TAG_AUDIO_EVENTS))
        self.tag_events_checkbox.setObjectName("dialogCheckboxFT")
        checkbox_layout.addWidget(self.tag_events_checkbox)
        checkbox_layout.addStretch(1)
        main_layout.addLayout(checkbox_layout)

        main_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        # 创建按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.addStretch()
        self.confirm_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        self.reset_button = QPushButton("重置")
        self.confirm_button.clicked.connect(self._accept_settings)
        self.cancel_button.clicked.connect(self.reject)
        self.reset_button.clicked.connect(self._reset_settings)
        button_layout.addWidget(self.confirm_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        self._apply_styles()
        self.resize(600, 420)

        # 检查是否已有批量文件需要处理
        if hasattr(current_settings, 'get') and current_settings.get('audio_files'):
            # 如果传入设置中已有批量文件，进行相应的UI设置
            self.selected_audio_files = current_settings.get('audio_files', [])
            if self.selected_audio_files:
                self.selected_audio_file_path = ""  # 清空单个文件路径
                self.audio_file_path_entry.setText(f"已选择 {len(self.selected_audio_files)} 个音频文件")
                # 确保批量模式下控件是可用的
                self.language_combo.setEnabled(True)
                self.num_speakers_combo.setEnabled(True)

    def _browse_audio_file(self):
        """浏览并选择音频文件，支持单文件和多文件选择模式"""
        start_dir = os.path.dirname(self.selected_audio_file_path) \
            if self.selected_audio_file_path and os.path.exists(os.path.dirname(self.selected_audio_file_path)) \
            else os.path.expanduser("~")

        supported_formats = "音频文件 (*.mp3 *.wav *.flac *.m4a *.ogg *.opus *.aac *.webm *.mp4 *.mov);;所有文件 (*.*)"
        filepaths, _ = QFileDialog.getOpenFileNames(self, "选择音频文件", start_dir, supported_formats)

        if filepaths:
            if len(filepaths) == 1:
                # 单个文件模式
                self.selected_audio_file_path = filepaths[0]
                self.selected_audio_files = []  # 清空批量文件列表
                self.audio_file_path_entry.setText(filepaths[0])
                # 启用语言和说话人数选择
                self.language_combo.setEnabled(True)
                self.num_speakers_combo.setEnabled(True)
            else:
                # 批量文件模式
                self.selected_audio_files = filepaths
                self.selected_audio_file_path = ""  # 清空单个文件路径
                self.audio_file_path_entry.setText(f"已选择 {len(filepaths)} 个音频文件")
                # 批量音频模式下允许用户调整参数，不强制禁用选项
                # 保持用户之前的选择或使用默认值
                # 只有在用户明确需要时才使用自动检测
                # 确保控件在批量模式下是可用的
                self.language_combo.setEnabled(True)
                self.num_speakers_combo.setEnabled(True)

    def _accept_settings(self):
        """验证并应用用户的设置配置"""
        # 检查文件选择情况
        if not self.selected_audio_file_path and not self.selected_audio_files:
            error_dialog = QMessageBox(self)
            error_dialog.setWindowTitle("错误")
            error_dialog.setText("请选择一个有效的音频文件。")
            error_dialog.setIcon(QMessageBox.Icon.Warning)
            error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
            error_dialog.exec()
            return

        # 单个文件模式验证
        if self.selected_audio_file_path and not os.path.exists(self.selected_audio_file_path):
            error_dialog = QMessageBox(self)
            error_dialog.setWindowTitle("错误")
            error_dialog.setText("请选择一个有效的音频文件。")
            error_dialog.setIcon(QMessageBox.Icon.Warning)
            error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
            error_dialog.exec()
            return

        # 批量文件模式验证
        if self.selected_audio_files:
            valid_files = []
            for filepath in self.selected_audio_files:
                if os.path.exists(filepath):
                    valid_files.append(filepath)
                else:
                    error_dialog = QMessageBox(self)
                    error_dialog.setWindowTitle("错误")
                    error_dialog.setText(f"文件不存在: {filepath}")
                    error_dialog.setIcon(QMessageBox.Icon.Warning)
                    error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
                    error_dialog.exec()
                    return

            if not valid_files:
                error_dialog = QMessageBox(self)
                error_dialog.setWindowTitle("错误")
                error_dialog.setText("没有选择有效的音频文件。")
                error_dialog.setIcon(QMessageBox.Icon.Warning)
                error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
                error_dialog.exec()
                return

        # 获取设置参数
        lang_display_to_api = {"自动检测": "auto", "日语": "ja", "中文": "zh", "英文": "en", "韩语": "ko"}
        selected_lang_display = self.language_combo.currentText()

        new_settings = {
            'audio_file_path': self.selected_audio_file_path,
            'audio_files': self.selected_audio_files,  # 批量音频文件列表
            'language': lang_display_to_api.get(selected_lang_display, DEFAULT_FREE_TRANSCRIPTION_LANGUAGE),
            'num_speakers': self.num_speakers_combo.currentData(),
            'tag_audio_events': self.tag_events_checkbox.isChecked(),
        }
        self.settings_confirmed.emit(new_settings)
        self.accept()

    def _reset_settings(self):
        """重置所有设置为默认值"""
        # 清空音频文件选择
        self.selected_audio_file_path = ""
        self.selected_audio_files = []
        self.audio_file_path_entry.setText("")

        # 启用语言和说话人数选择
        self.language_combo.setEnabled(True)
        self.num_speakers_combo.setEnabled(True)

        # 重置语言选择
        lang_map_to_display = {"auto": "自动检测", "ja": "日语", "zh": "中文", "en": "英文", "ko": "韩语"}
        default_display_lang = lang_map_to_display.get(DEFAULT_FREE_TRANSCRIPTION_LANGUAGE, "自动检测")
        self.language_combo.setCurrentText(default_display_lang)

        # 重置说话人数选择
        default_num_speaker_index = self.num_speakers_combo.findData(DEFAULT_FREE_TRANSCRIPTION_NUM_SPEAKERS)
        if default_num_speaker_index != -1:
             self.num_speakers_combo.setCurrentIndex(default_num_speaker_index)
        else:
             self.num_speakers_combo.setCurrentText("自动检测")

        # 重置音频事件标记
        self.tag_events_checkbox.setChecked(DEFAULT_FREE_TRANSCRIPTION_TAG_AUDIO_EVENTS)

    def _apply_styles(self):
        # 借鉴 SettingsDialog 的样式
        # 并为新对话框的特定控件添加或调整样式
        style = f"""
            CustomLabel {{ /* 由 setCustomColors 控制颜色 */
                background-color: transparent;
            }}
            QLineEdit#pathEditDialogFT {{ /* 为音频路径输入框定制 */
                background-color: rgba(255, 255, 255, 50); 
                color: #EAEAEA; 
                border: 1px solid rgba(135, 206, 235, 120); 
                border-radius: 5px;
                padding: 5px; 
                font-family: 'Microsoft YaHei'; font-size: 12pt; /* 稍大一点 */
            }}
            QComboBox#dialogComboBoxFT {{ /* 为下拉框定制 */
                background-color: rgba(255, 255, 255, 50); 
                color: #EAEAEA;
                border: 1px solid rgba(135, 206, 235, 120); 
                border-radius: 5px;
                padding: 5px 8px; 
                font-family: 'Microsoft YaHei'; font-size: 12pt; /* 稍大一点 */
                min-height: 1.9em; /* 调整最小高度以匹配QLineEdit */
            }}
            QComboBox#dialogComboBoxFT::drop-down {{
                subcontrol-origin: padding; subcontrol-position: center right;
                width: 22px; /* 稍宽一点 */
                border-left: 1px solid rgba(135, 206, 235, 120);
            }}
            /* 如果需要自定义箭头图标，可以像 SettingsDialog 中那样添加 */
            
            QCheckBox#dialogCheckboxFT {{ /* 为复选框定制 */
                color: #E0E8F0; /* 浅色字体 */
                font-family: '楷体'; font-size: 14pt; font-weight: bold; /* 更清晰的字体 */
                spacing: 8px;
                background-color: transparent;
                padding: 5px 0px; /* 上下一点padding */
            }}
            QCheckBox#dialogCheckboxFT::indicator {{
                width: 20px; height: 20px; /* 稍大一点的指示器 */
                border: 1px solid rgba(135, 206, 235, 180);
                border-radius: 4px;
                background-color: rgba(255,255,255,40);
            }}
            QCheckBox#dialogCheckboxFT::indicator:checked {{
                background-color: rgba(100, 180, 230, 200); /* 更亮的选中色 */
                image: url('{resource_path('checkmark.png').replace(os.sep, '/') if resource_path('checkmark.png') and os.path.exists(resource_path('checkmark.png')) else "" }');
                background-repeat: no-repeat;
                background-position: center;
            }}

            QPushButton {{ /* 与 SettingsDialog 按钮样式一致 */
                background-color: rgba(100, 149, 237, 170); color: white;
                border: 1px solid rgba(135, 206, 235, 100);
                border-radius: 6px;
                font-family: '楷体'; font-weight: bold; font-size: 14pt;
                padding: 8px 20px;
                min-width: 80px;
            }}
            QPushButton:hover {{ background-color: rgba(120, 169, 247, 200); }}
            QPushButton:pressed {{ background-color: rgba(80, 129, 217, 200); }}

            QPushButton#dialogBrowseButton {{ /* 浏览按钮特定样式 */
                font-size: 12pt; /* 稍小一点 */
                padding: 6px 15px;
                min-width: 70px;
                 background-color: rgba(120, 170, 130, 170); /* 不同颜色以区分 */
            }}
             QPushButton#dialogBrowseButton:hover {{ background-color: rgba(140, 190, 150, 200); }}
             QPushButton#dialogBrowseButton:pressed {{ background-color: rgba(100, 150, 110, 200); }}


            QPushButton#dialogCloseButton {{ /* 与 SettingsDialog 关闭按钮一致 */
                background-color: rgba(255, 99, 71, 160); color: white;
                border: none; border-radius: 15px; 
                font-weight:bold; font-size: 12pt; 
                padding: 0px; min-width: 30px; max-width:30px; min-height:30px; max-height:30px;
            }}
            QPushButton#dialogCloseButton:hover {{ background-color: rgba(255, 99, 71, 200); }}
        """
        self.setStyleSheet(style)
        
        # 下拉箭头图标 (如果 SettingsDialog 有，这里也保持一致)
        # up_arrow_path_str = resource_path('up_arrow.png') # 这些是spinbox的，combobox用另一个
        # down_arrow_path_str = resource_path('down_arrow.png')
        dropdown_arrow_path_str = resource_path('dropdown_arrow.png') # 假设有这个图标
        qss_dropdown_arrow = ""
        if dropdown_arrow_path_str and os.path.exists(dropdown_arrow_path_str):
            qss_dropdown_arrow = f"url('{dropdown_arrow_path_str.replace(os.sep, '/')}')"

        combo_style_sheet = self.language_combo.styleSheet() # 获取基础样式
        combo_style_sheet += f"""
            QComboBox#dialogComboBoxFT::down-arrow {{
                image: {qss_dropdown_arrow if qss_dropdown_arrow else "none"};
                width: 10px; height: 10px; /* 调整箭头大小 */
                padding-right: 5px; /* 箭头右边距 */
            }}
            QComboBox#dialogComboBoxFT QAbstractItemView {{ /* 下拉菜单样式，参考主窗口 */
                background-color: rgba(70, 70, 90, 240); /* 深色背景 */
                color: #EAEAEA; 
                border: 1px solid rgba(135, 206, 235, 150); 
                border-radius:5px; padding:4px; outline:0px;
                selection-background-color: rgba(100, 149, 237, 190); /* 选中项背景 */
            }}
        """
        self.language_combo.setStyleSheet(combo_style_sheet)
        self.num_speakers_combo.setStyleSheet(combo_style_sheet)


    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self, 'container') and self.container.layout().itemAt(0) and \
               event.position().y() < (self.container.layout().itemAt(0).geometry().height() + \
                                        self.container.layout().contentsMargins().top()):
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
        if hasattr(self, 'is_dragging_dialog'):
            self.is_dragging_dialog = False
        super().mouseReleaseEvent(event)