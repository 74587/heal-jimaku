"""
用户友好的日志处理器

将技术日志消息转换为小白用户能理解的语言
提供进度状态、错误提示和操作指导
"""

import re
from typing import Dict, Optional, Tuple
from enum import Enum


class MessageLevel(Enum):
    """消息级别"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    PROGRESS = "progress"


class UserFriendlyLogger:
    """用户友好的日志处理器"""

    def __init__(self):
        # 初始化消息映射字典
        self._init_message_mappings()

    def _init_message_mappings(self):
        """初始化技术消息到用户友好消息的映射"""

        # 阶段描述映射
        self.stage_messages = {
            # 免费转录阶段
            "正在开始免费在线转录": "🎵 准备开始音频转录...",
            "正在上传音频文件": "📤 正在上传音频文件...",
            "ElevenLabs Web转录": "🎙️ 正在使用AI识别语音内容...",
            "转录结果已保存到": "✅ 语音识别完成，正在处理字幕...",

            # 云端转录阶段
            "开始云端转录": "☁️ 连接到云端语音识别服务...",
            "使用ElevenLabs": "🎙️ 使用高级语音识别引擎...",
            "使用Soniox": "🎯 使用高精度语音分析...",
            "云端数据清理": "🔒 正在保护您的隐私数据...",

            # SRT处理阶段
            "正在解析转录结果": "📝 分析语音识别结果...",
            "正在生成SRT字幕": "⏰ 正在生成时间轴字幕...",
            "正在优化字幕条目": "✨ 优化字幕显示效果...",
            "正在进行AI纠错": "🧠 使用AI智能校对字幕...",
            "字幕生成完成": "🎉 字幕制作完成！",

            # 文件操作
            "文件已保存": "💾 文件已成功保存",
            "正在保存文件": "💾 正在保存结果文件...",

            # 配置和设置
            "正在同步配置": "⚙️ 加载配置信息...",
            "参数已更新": "✅ 设置已更新",
        }

        # 错误消息映射
        self.error_messages = {
            # 文件相关错误
            "文件不存在": "❌ 找不到指定的文件，请检查文件路径",
            "权限不足": "❌ 没有文件访问权限，请检查文件夹设置",
            "磁盘空间不足": "❌ 磁盘空间不足，请清理后重试",
            "文件格式不支持": "❌ 不支持的文件格式，请使用MP3、WAV等音频文件",

            # 网络相关错误
            "网络连接失败": "🌐 网络连接失败，请检查网络设置",
            "API调用失败": "🔗 服务暂时不可用，请稍后重试",
            "认证失败": "🔑 API密钥无效，请检查设置",
            "请求超时": "⏰ 请求超时，请检查网络连接",

            # 转录相关错误
            "转录失败": "🎙️ 语音识别失败，请检查音频质量",
            "音频质量过低": "🔊 音频质量过低，建议使用更清晰的录音",
            "语音无法识别": "🗣️ 无法识别语音内容，请检查音频文件",

            # 系统相关错误
            "内存不足": "💾 内存不足，请关闭其他程序后重试",
            "系统错误": "⚠️ 系统出现错误，请重启程序",
        }

        # 进度描述映射
        self.progress_messages = {
            "正在初始化": "🚀 准备就绪...",
            "正在处理": "⚙️ 处理中...",
            "正在分析": "🔍 分析中...",
            "正在生成": "✨ 生成中...",
            "正在保存": "💾 保存中...",
            "正在清理": "🧹 清理中...",
            "正在完成": "🏁 即将完成...",
        }

        # 成功消息映射
        self.success_messages = {
            "任务完成": "🎉 任务完成！",
            "保存成功": "✅ 保存成功！",
            "处理成功": "👍 处理成功！",
            "连接成功": "🌟 连接成功！",
        }

    def translate_message(self, original_message: str) -> Tuple[str, MessageLevel]:
        """
        将技术消息转换为用户友好的消息

        Args:
            original_message: 原始技术消息

        Returns:
            Tuple[str, MessageLevel]: (用户友好消息, 消息级别)
        """
        message_lower = original_message.lower()

        # 检查错误消息
        for error_key, user_message in self.error_messages.items():
            if error_key in original_message:
                return user_message, MessageLevel.ERROR

        # 检查成功消息
        for success_key, user_message in self.success_messages.items():
            if success_key in original_message:
                return user_message, MessageLevel.SUCCESS

        # 检查阶段消息
        for stage_key, user_message in self.stage_messages.items():
            if stage_key in original_message:
                return user_message, MessageLevel.PROGRESS

        # 检查进度消息
        for progress_key, user_message in self.progress_messages.items():
            if progress_key in original_message:
                return user_message, MessageLevel.INFO

        # 特殊模式的消息转换
        translated = self._handle_special_patterns(original_message)
        if translated:
            return translated, MessageLevel.INFO

        # 默认情况下，保持原消息但简化技术术语
        simplified = self._simplify_technical_terms(original_message)
        return simplified, MessageLevel.INFO

    def _handle_special_patterns(self, message: str) -> Optional[str]:
        """处理特殊的消息模式"""

        # API配置信息 - 隐藏技术细节
        if "API配置" in message or "api_key" in message.lower():
            return "🔑 正在配置API连接..."

        # 参数同步
        if "同步参数" in message or "sync" in message.lower():
            return "⚙️ 正在加载设置..."

        # 百分比进度
        if "%" in message:
            percentage_match = re.search(r'(\d+)%', message)
            if percentage_match:
                percentage = percentage_match.group(1)
                return f"📊 进度：{percentage}%"

        # 时间信息
        if any(word in message for word in ["秒", "分钟", "小时"]):
            return f"⏱️ {message}"

        # 文件路径 - 只显示文件名
        if "保存到:" in message or "path" in message.lower():
            parts = message.split("保存到:")[-1].strip()
            if "\\" in parts or "/" in parts:
                filename = parts.split("\\")[-1].split("/")[-1]
                return f"💾 已保存：{filename}"

        return None

    def _simplify_technical_terms(self, message: str) -> str:
        """简化技术术语"""

        # 移除模块标记
        cleaned = re.sub(r'\[.*?\]\s*', '', message)

        # 替换技术术语
        replacements = {
            "转录": "语音识别",
            "JSON": "数据",
            "SRT": "字幕",
            "API": "服务",
            "配置": "设置",
            "参数": "选项",
            "初始化": "准备",
            "清理": "整理",
            "同步": "更新",
            "对齐": "调整",
            "合并": "整合",
            "分割": "分段",
            "优化": "改善",
        }

        for tech_term, user_term in replacements.items():
            cleaned = cleaned.replace(tech_term, user_term)

        return cleaned.strip()

    def get_progress_stage_emoji(self, stage: str) -> str:
        """根据处理阶段获取对应的emoji"""
        stage_emoji = {
            "upload": "📤",
            "transcribe": "🎙️",
            "parse": "📝",
            "process": "⚙️",
            "generate": "✨",
            "save": "💾",
            "complete": "🎉",
            "error": "❌",
            "warning": "⚠️",
        }
        return stage_emoji.get(stage.lower(), "📋")

    def format_user_message(self, message: str, include_time: bool = True) -> str:
        """
        格式化用户友好的消息

        Args:
            message: 原始消息
            include_time: 是否包含时间戳

        Returns:
            str: 格式化后的用户友好消息
        """
        user_message, level = self.translate_message(message)

        # 根据级别添加前缀
        if level == MessageLevel.ERROR:
            prefix = "❌ "
        elif level == MessageLevel.SUCCESS:
            prefix = "✅ "
        elif level == MessageLevel.WARNING:
            prefix = "⚠️ "
        elif level == MessageLevel.PROGRESS:
            prefix = "🔄 "
        else:
            prefix = "ℹ️ "

        formatted_message = f"{prefix}{user_message}"

        return formatted_message


# 全局实例
user_logger = UserFriendlyLogger()