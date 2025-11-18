"""
转录数据解析器模块

负责解析来自不同ASR（自动语音识别）服务商的JSON输出格式。
支持 ElevenLabs、Whisper、Deepgram、AssemblyAI 等多种数据源。
提供统一的接口将不同格式的转录数据转换为内部标准格式。

作者: Heal-Jimaku Project
版本: 1.3.0
"""

from typing import List, Optional, Literal
import traceback
# Corrected import: removed 'src.' prefix, or use relative if preferred for sibling modules
from core.data_models import TimestampedWord, ParsedTranscription
# from .data_models import TimestampedWord, ParsedTranscription # Alternative using relative import


class TranscriptionParser:
    """解析来自不同ASR服务商的JSON输出。"""
    def __init__(self, signals_forwarder=None):
        self._signals = signals_forwarder # 用于日志输出的信号转发器

    def log(self, message):
        """记录日志消息。"""
        if self._signals and hasattr(self._signals, 'log_message') and hasattr(self._signals.log_message, 'emit'):
            self._signals.log_message.emit(f"[Parser] {message}")
        else:
            print(f"[Parser] {message}") # 如果没有信号转发器，则打印到控制台

    def parse(self, data: dict, source_format: Literal["elevenlabs", "whisper", "deepgram", "assemblyai"]) -> Optional[ParsedTranscription]:
        """
        解析JSON数据。
        :param data: 包含ASR结果的字典。
        :param source_format: JSON的来源格式。
        :return: 解析后的转录数据对象，或在失败时返回None。
        """
        self.log(f"开始解析 {source_format.capitalize()} JSON...")
        result: Optional[ParsedTranscription] = None
        try:
            if source_format == "elevenlabs": result = self._parse_elevenlabs(data)
            elif source_format == "whisper": result = self._parse_whisper(data)
            elif source_format == "deepgram": result = self._parse_deepgram(data)
            elif source_format == "assemblyai": result = self._parse_assemblyai(data)
            else:
                self.log(f"错误: 不支持的 JSON 格式源 '{source_format}'")
                return None

            if result:
                self.log(f"{source_format.capitalize()} JSON 解析完成，得到 {len(result.words)} 个词。总文本长度: {len(result.full_text or '')} 字符。")
            else:
                self.log(f"{source_format.capitalize()} JSON 解析未能返回有效结果。")
            return result
        except Exception as e:
            self.log(f"解析 {source_format.capitalize()} JSON 时出错: {e}")
            self.log(traceback.format_exc())
            return None

    def _parse_elevenlabs(self, data: dict) -> Optional[ParsedTranscription]:
        """解析 ElevenLabs 格式的JSON。"""
        parsed_words: List[TimestampedWord] = []
        for word_info in data.get("words", []):
            text = word_info.get("text", word_info.get("word")) # 兼容 'text' 和 'word' 字段
            start = word_info.get("start")
            end = word_info.get("end")
            speaker = word_info.get("speaker_id", word_info.get("speaker")) # 兼容 'speaker_id' 和 'speaker'
            if text is not None and start is not None and end is not None:
                try:
                    parsed_words.append(TimestampedWord(str(text), float(start), float(end), str(speaker) if speaker else None))
                except ValueError:
                    self.log(f"警告: 跳过 ElevenLabs 词条，时间戳格式无效: {word_info}")
            else:
                self.log(f"警告: 跳过不完整的 ElevenLabs 词条: {word_info}")
        full_text = data.get("text", "") # 获取完整文本
        if not full_text and parsed_words:
            full_text = " ".join(word.text for word in parsed_words) # 如果没有完整文本，则从词语拼接
        language = data.get("language_code", data.get("language")) # 获取语言代码
        return ParsedTranscription(words=parsed_words, full_text=full_text, language_code=language)

    def _parse_whisper(self, data: dict) -> Optional[ParsedTranscription]:
        """解析 Whisper (OpenAI) 格式的JSON。"""
        parsed_words: List[TimestampedWord] = []
        whisper_words_list: list = []
        # Whisper 的词列表可能在顶层 "words" 或嵌套在 "segments" 下
        if "words" in data and isinstance(data["words"], list):
            whisper_words_list = data["words"]
        elif "segments" in data and isinstance(data["segments"], list):
            for segment in data.get("segments", []):
                if "words" in segment and isinstance(segment["words"], list):
                    whisper_words_list.extend(segment["words"])

        if not whisper_words_list: # 如果没有词列表，尝试获取仅有的完整文本
            full_text_only = data.get("text")
            if full_text_only:
                return ParsedTranscription(words=[], full_text=full_text_only, language_code=data.get("language"))
            self.log("错误: Whisper JSON 既无有效词列表也无顶层文本。")
            return None

        for word_info in whisper_words_list:
            text = word_info.get("word", word_info.get("text")) # 兼容 'word' 和 'text'
            start = word_info.get("start")
            end = word_info.get("end")
            if text is not None and start is not None and end is not None:
                try:
                    parsed_words.append(TimestampedWord(str(text), float(start), float(end)))
                except ValueError:
                    self.log(f"警告: 跳过 Whisper 词条，时间戳格式无效: {word_info}")
            else:
                self.log(f"警告: 跳过不完整的 Whisper 词条: {word_info}")
        full_text = data.get("text", "")
        if not full_text and parsed_words:
            full_text = " ".join(word.text for word in parsed_words)
        language = data.get("language")
        return ParsedTranscription(words=parsed_words, full_text=full_text, language_code=language)

    def _parse_deepgram(self, data: dict) -> Optional[ParsedTranscription]:
        """解析 Deepgram 格式的JSON。"""
        try:
            # 检查 Deepgram JSON 的预期结构
            if not (data.get("results") and data["results"].get("channels") and isinstance(data["results"]["channels"], list) and
                    len(data["results"]["channels"]) > 0 and data["results"]["channels"][0].get("alternatives") and
                    isinstance(data["results"]["channels"][0]["alternatives"], list) and len(data["results"]["channels"][0]["alternatives"]) > 0):
                self.log("错误: Deepgram JSON 结构不符合预期。")
                return None

            alternative = data["results"]["channels"][0]["alternatives"][0] # 通常取第一个 alternative
            if "words" not in alternative or not isinstance(alternative["words"], list): # 如果没有词列表
                full_text_only = alternative.get("transcript", "") # 尝试获取 "transcript"
                if full_text_only:
                    return ParsedTranscription(words=[], full_text=full_text_only, language_code=data["results"]["channels"][0].get("detected_language"))
                self.log("错误: Deepgram JSON 既无词列表也无 transcript。")
                return None

            parsed_words: List[TimestampedWord] = []
            for word_info in alternative.get("words", []):
                text = word_info.get("word", word_info.get("punctuated_word")) # 优先使用 "punctuated_word"
                start = word_info.get("start")
                end = word_info.get("end")
                speaker = word_info.get("speaker")
                if text is not None and start is not None and end is not None:
                    try:
                        parsed_words.append(TimestampedWord(str(text), float(start), float(end), str(speaker) if speaker else None))
                    except ValueError:
                        self.log(f"警告: 跳过 Deepgram 词条，时间戳格式无效: {word_info}")
                else:
                    self.log(f"警告: 跳过不完整的 Deepgram 词条: {word_info}")
            full_text = alternative.get("transcript", "")
            if not full_text and parsed_words:
                full_text = " ".join(word.text for word in parsed_words)
            language = data["results"]["channels"][0].get("detected_language")
            return ParsedTranscription(words=parsed_words, full_text=full_text, language_code=language)
        except (KeyError, IndexError) as e:
            self.log(f"错误: 解析 Deepgram JSON 时键或索引错误: {e}")
            return None

    def _parse_assemblyai(self, data: dict) -> Optional[ParsedTranscription]:
        """解析 AssemblyAI 格式的JSON。"""
        parsed_words: List[TimestampedWord] = []
        assemblyai_words_list: list = []
        # AssemblyAI 的词列表可能在顶层 "words" 或嵌套在 "utterances" 下
        if "words" in data and isinstance(data["words"], list):
            assemblyai_words_list = data["words"]
        elif "utterances" in data and isinstance(data["utterances"], list):
            for utterance in data["utterances"]:
                if "words" in utterance and isinstance(utterance["words"], list):
                    assemblyai_words_list.extend(utterance["words"])

        if not assemblyai_words_list:
            full_text_only = data.get("text")
            if full_text_only:
                return ParsedTranscription(words=[], full_text=full_text_only, language_code=data.get("language_code"))
            self.log("错误: AssemblyAI JSON 既无有效词列表也无顶层文本。")
            return None

        for word_info in assemblyai_words_list:
            text = word_info.get("text")
            start_ms = word_info.get("start")
            end_ms = word_info.get("end")
            speaker = word_info.get("speaker")
            # AssemblyAI 时间戳以毫秒为单位，需要转换
            if text is not None and start_ms is not None and end_ms is not None:
                try:
                    parsed_words.append(TimestampedWord(str(text), float(start_ms)/1000.0, float(end_ms)/1000.0, str(speaker) if speaker else None))
                except ValueError:
                    self.log(f"警告: 跳过 AssemblyAI 词条，时间戳或ID格式无效: {word_info}")
            else:
                self.log(f"警告: 跳过不完整的 AssemblyAI 词条: {word_info}")
        full_text = data.get("text", "")
        if not full_text and parsed_words:
            full_text = " ".join(word.text for word in parsed_words)
        language = data.get("language_code")
        return ParsedTranscription(words=parsed_words, full_text=full_text, language_code=language)