"""
数据模型模块

定义了转录处理和字幕生成过程中使用的核心数据结构。
包含时间戳词、转录结果、字幕条目等基础数据类。
提供统一的数据格式用于各模块间的数据交换。

作者: Heal-Jimaku Project
版本: 1.3.0
"""

from dataclasses import dataclass, field
from typing import List, Optional
import re

# --- 统一的数据结构 ---
@dataclass
class TimestampedWord:
    """表示带时间戳的单个词。"""
    text: str # 词文本
    start_time: float # 开始时间 (秒)
    end_time: float # 结束时间 (秒)
    speaker_id: Optional[str] = None # 发言人ID (可选)

@dataclass
class ParsedTranscription:
    """表示解析后的ASR转录结果。"""
    words: List[TimestampedWord] # 词列表
    full_text: Optional[str] = None # 完整文本 (可选)
    language_code: Optional[str] = None # 语言代码 (可选)

# --- 字幕条目类 ---
class SubtitleEntry:
    """表示一条SRT字幕。"""
    def __init__(self, index, start_time, end_time, text, words_used: Optional[List[TimestampedWord]] = None, alignment_ratio=1.0):
        self.index = index # 字幕序号
        self.start_time = start_time # 开始时间
        self.end_time = end_time # 结束时间
        self.text = re.sub(r'\s+', ' ', text).strip() # 文本内容 (去除多余空格并剥离首尾空格)
        self.words_used = words_used if words_used else [] # 使用的词对象列表 (用于调试和高级处理)
        self.alignment_ratio = alignment_ratio # 对齐比率 (LLM片段与ASR词的相似度)
        self.is_intentionally_oversized = False # 标记是否故意超限 (例如无法合理分割的长句)

    @property
    def duration(self):
        """计算字幕持续时间。"""
        if self.start_time is not None and self.end_time is not None: return max(0, self.end_time - self.start_time)
        return 0

    def to_srt_format(self, processor_instance): # processor_instance 是 SrtProcessor 实例
        """将字幕条目转换为SRT格式的字符串。"""
        if self.start_time is None or self.end_time is None or self.text is None:
            # processor_instance.log(f"警告: 字幕条目 {self.index} 缺少时间或文本") # Log将在 SrtProcessor 中处理
            return "" # 返回空字符串或抛出异常，取决于错误处理策略
        # 确保结束时间至少比开始时间晚1毫秒
        # 此逻辑也移到 SrtProcessor 的最终格式化阶段，以避免重复记录和确保一致性
        # if self.end_time < self.start_time + 0.001:
        #     # processor_instance.log(f"警告: 字幕条目 {self.index} 结束时间 ({processor_instance.format_timecode(self.end_time)}) 早于或等于开始时间 ({processor_instance.format_timecode(self.start_time)})。已修正为开始时间 +0.1秒。")
        #     self.end_time = self.start_time + 0.1 # 0.1 秒可能太长，改为0.001

        # format_timecode 将由 processor_instance 调用
        start_tc = processor_instance.format_timecode(self.start_time)
        end_tc = processor_instance.format_timecode(self.end_time)
        return f"{self.index}\n{start_tc} --> {end_tc}\n{self.text}\n\n"