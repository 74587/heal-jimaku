"""
SRT字幕处理器模块

负责将ASR（自动语音识别）转录结果转换为标准的SRT字幕格式。
包含智能文本分割、时间戳精确对齐、字幕条目优化等核心功能。
支持多语言处理和自定义参数配置。

作者: Heal-Jimaku Project
版本: 1.3.0
"""

import re
import difflib
from typing import List, Optional, Any, Dict
from .data_models import TimestampedWord, ParsedTranscription, SubtitleEntry
import config as app_config # 使用别名以减少潜在冲突并清晰化来源

class SrtProcessor:
    """
    SRT字幕处理器

    负责将ASR转录结果转换为SRT字幕格式，包括文本分割、时间戳对齐、
    字幕优化等核心功能。
    """
    def __init__(self, initial_config: Optional[Dict[str, Any]] = None):
        self._signals: Optional[Any] = None
        self._current_progress_offset: int = 0
        self._current_progress_range: int = 100

        # 初始化SRT处理参数的默认值
        self.min_duration_target: float = app_config.DEFAULT_MIN_DURATION_TARGET
        self.max_duration: float = app_config.DEFAULT_MAX_DURATION
        self.max_chars_per_line: int = app_config.DEFAULT_MAX_CHARS_PER_LINE
        self.default_gap_ms: int = app_config.DEFAULT_DEFAULT_GAP_MS

        # 初始化LLM配置相关的成员变量
        self.llm_api_key: Optional[str] = app_config.DEFAULT_LLM_API_KEY
        self.llm_base_url: Optional[str] = app_config.DEFAULT_LLM_API_BASE_URL
        self.llm_model_name: Optional[str] = app_config.DEFAULT_LLM_MODEL_NAME
        self.llm_temperature: float = app_config.DEFAULT_LLM_TEMPERATURE

        if initial_config:
            self.configure_from_main_config(initial_config)

    def set_signals_forwarder(self, signals_forwarder: Any):
        self._signals = signals_forwarder

    def configure_from_main_config(self, main_config_data: Dict[str, Any]):
        """
        Update SRT processor parameters from main application configuration.

        Args:
            main_config_data: Dictionary containing configuration values using USER_..._KEY constants
        """
        # Update SRT parameters using USER_..._KEY from main configuration
        self.min_duration_target = float(main_config_data.get(app_config.USER_MIN_DURATION_TARGET_KEY, app_config.DEFAULT_MIN_DURATION_TARGET))
        self.max_duration = float(main_config_data.get(app_config.USER_MAX_DURATION_KEY, app_config.DEFAULT_MAX_DURATION))
        self.max_chars_per_line = int(main_config_data.get(app_config.USER_MAX_CHARS_PER_LINE_KEY, app_config.DEFAULT_MAX_CHARS_PER_LINE))
        self.default_gap_ms = int(main_config_data.get(app_config.USER_DEFAULT_GAP_MS_KEY, app_config.DEFAULT_DEFAULT_GAP_MS))

        # Update LLM parameters using new multi-profile system
        current_llm_profile = app_config.get_current_llm_profile(main_config_data)
        self.llm_api_key = current_llm_profile.get("api_key", app_config.DEFAULT_LLM_API_KEY)
        self.llm_base_url = current_llm_profile.get("api_base_url", app_config.DEFAULT_LLM_API_BASE_URL)
        self.llm_model_name = current_llm_profile.get("model_name", app_config.DEFAULT_LLM_MODEL_NAME)
        self.llm_temperature = float(current_llm_profile.get("temperature", app_config.DEFAULT_LLM_TEMPERATURE))

    # --- 新增/恢复 update_srt_params 方法 ---
    def update_srt_params(self, srt_params_dict: Dict[str, Any]):
        """
        Update SRT processing parameters from a simple dictionary.

        This method is called by MainWindow.start_conversion() with parameters
        from self.advanced_srt_settings.

        Args:
            srt_params_dict: Dictionary containing SRT processing parameters
        """
        self.min_duration_target = float(srt_params_dict.get('min_duration_target', self.min_duration_target))
        self.max_duration = float(srt_params_dict.get('max_duration', self.max_duration))
        self.max_chars_per_line = int(srt_params_dict.get('max_chars_per_line', self.max_chars_per_line))
        self.default_gap_ms = int(srt_params_dict.get('default_gap_ms', self.default_gap_ms))


    def update_llm_config(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ):
        self.log("正在单独更新 SrtProcessor 的LLM API参数...")
        if api_key is not None: self.llm_api_key = api_key
        if base_url is not None: self.llm_base_url = base_url
        if model is not None: self.llm_model_name = model
        if temperature is not None: self.llm_temperature = float(temperature)
        self.log(f"  LLM参数单独更新后: BaseURL='{self.llm_base_url}', Model='{self.llm_model_name}', Temp={self.llm_temperature}, APIKeySet={bool(self.llm_api_key)}")

    def get_current_llm_config_for_api_call(self) -> Dict[str, Any]:
        return {
            "api_key": self.llm_api_key,
            "custom_api_base_url_str": self.llm_base_url,
            "custom_model_name": self.llm_model_name,
            "custom_temperature": self.llm_temperature,
        }

    def log(self, message: str):
        if self._signals and hasattr(self._signals, 'log_message') and hasattr(self._signals.log_message, 'emit'):
            self._signals.log_message.emit(f"[SRT Processor] {message}")
        else:
            print(f"[SRT Processor] {message}")

    def _is_worker_running(self) -> bool: 
        if self._signals and hasattr(self._signals, 'parent') and \
           hasattr(self._signals.parent(), 'is_running'): 
            return self._signals.parent().is_running
        return True

    def _emit_srt_progress(self, current_step: int, total_steps: int):
        if total_steps == 0:
            internal_percentage = 100
        else:
            internal_percentage = min(int((current_step / total_steps) * 100), 100)
        
        if self._signals and hasattr(self._signals, 'progress') and hasattr(self._signals.progress, 'emit'):
            global_progress = self._current_progress_offset + int(internal_percentage * (self._current_progress_range / 100.0))
            capped_progress = min(max(global_progress, self._current_progress_offset), self._current_progress_offset + self._current_progress_range)
            capped_progress = min(capped_progress, 99) 
            self._signals.progress.emit(capped_progress)

    def _is_bracketed_content(self, text: str) -> bool:
        """检查文本是否为括号内容（任何括号内的内容都应该独立处理）"""
        if not text or not text.strip():
            return False

        text = text.strip()

        # 检查是否完全被括号包围
        # 支持各种括号类型：()、（）、【】、[]、{}、<>
        bracket_patterns = [
            r"^\(.*\)$",      # ()
            r"^（.*）$",        # （）
            r"^【.*】$",        # 【】
            r"^\[.*\]$",        # []
            r"^\{.*\}$",        # {}
            r"^<.*>$",          # <>
        ]

        return any(re.match(pattern, text) for pattern in bracket_patterns)

    def _is_audio_event_words(self, words_list) -> bool:
        """检查词列表是否为括号内容（代表非语言声音或特殊标记）"""
        if not words_list:
            return False

        # 组合所有词的文本
        full_text = "".join([w.text for w in words_list]).strip()

        # 检查是否为括号内容
        if self._is_bracketed_content(full_text):
            return True

        # 如果ASR标记为audio_event类型，也认为是音频事件
        return any(getattr(w, 'type', 'word') == 'audio_event' for w in words_list)

    def format_timecode(self, seconds_float: float) -> str:
        if not isinstance(seconds_float, (int, float)) or seconds_float < 0:
            return "00:00:00,000"
        total_seconds_int = int(seconds_float)
        milliseconds = int(round((seconds_float - total_seconds_int) * 1000))
        if milliseconds >= 1000:
            total_seconds_int += 1
            milliseconds = 0
        hours = total_seconds_int // 3600
        minutes = (total_seconds_int % 3600) // 60
        seconds = total_seconds_int % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def check_word_has_punctuation(self, word_text: str, punctuation_set: set) -> bool:
        cleaned_text = word_text.strip()
        if not cleaned_text:
            return False
        for punct in punctuation_set:
            if cleaned_text.endswith(punct):
                return True
        return False

    def get_segment_words_fuzzy(self, text_segment: str, all_parsed_words: List[TimestampedWord], start_search_index: int) -> tuple[List[TimestampedWord], int, float]:
        """
        Fuzzy matching algorithm for aligning LLM segments with ASR word timestamps.

        Args:
            text_segment: LLM-generated text segment to align
            all_parsed_words: List of ASR words with timestamps
            start_search_index: Starting index in the word list for search

        Returns:
            Tuple of (matched_words, next_search_index, match_ratio)
        """
        segment_clean = text_segment.strip().replace(" ", "")
        if not segment_clean:
            return [], start_search_index, 0.0

        best_match_words_ts_objects: List[TimestampedWord] = []
        best_match_ratio = 0.0
        best_match_end_index = start_search_index

        # 使用适当的搜索窗口大小
        base_len_factor = 3
        min_additional_words = 20
        max_additional_words = 60
        estimated_words_in_segment = len(text_segment.split())
        search_window_size = len(segment_clean) * base_len_factor + min(max(estimated_words_in_segment * 2, min_additional_words), max_additional_words)
        max_lookahead_outer = min(start_search_index + search_window_size, len(all_parsed_words))

        for i in range(start_search_index, max_lookahead_outer):
            if not self._is_worker_running():
                break

            current_words_text_list = []
            current_word_ts_object_list: List[TimestampedWord] = []
            max_j_lookahead = min(i + len(segment_clean) + 30, len(all_parsed_words))

            for j in range(i, max_j_lookahead):
                word_obj = all_parsed_words[j]
                current_word_ts_object_list.append(word_obj)
                current_words_text_list.append(word_obj.text.replace(" ", ""))
                built_text = "".join(current_words_text_list)

                if not built_text.strip():
                    continue

                matcher = difflib.SequenceMatcher(None, segment_clean, built_text, autojunk=False)
                ratio = matcher.ratio()

                update_best = False
                if ratio > best_match_ratio:
                    update_best = True
                elif abs(ratio - best_match_ratio) < 1e-9:
                    if best_match_words_ts_objects:
                        current_len_diff = abs(len(built_text) - len(segment_clean))
                        best_len_diff = abs(len("".join(w.text.replace(" ","") for w in best_match_words_ts_objects)) - len(segment_clean))
                        if current_len_diff < best_len_diff:
                            update_best = True
                    else:
                        update_best = True

                if update_best and ratio > 0.01:
                    best_match_ratio = ratio
                    best_match_words_ts_objects = list(current_word_ts_object_list)
                    best_match_end_index = j + 1

                if ratio > 0.95 and len(built_text) > len(segment_clean) * 1.8:
                    break

            if best_match_ratio > 0.98:
                break

        if not best_match_words_ts_objects:
            self.log(f"严重警告: LLM片段 \"{text_segment}\" (清理后: \"{segment_clean}\") 无法在ASR词语中找到任何匹配。将跳过此片段。搜索起始索引: {start_search_index}")
            return [], start_search_index, 0.0

        if best_match_ratio < app_config.ALIGNMENT_SIMILARITY_THRESHOLD:
            matched_text_preview = "".join([w.text for w in best_match_words_ts_objects])
            self.log(f"警告: LLM片段 \"{text_segment}\" (清理后: \"{segment_clean}\") 与ASR词语的对齐相似度较低 ({best_match_ratio:.2f})。ASR匹配文本: \"{matched_text_preview}\"")

        return best_match_words_ts_objects, best_match_end_index, best_match_ratio

    # --- 结束时间修正 辅助函数 ---
    def _apply_end_time_correction(self, segment_words: List[TimestampedWord], raw_end_time: float, segment_start_time: float) -> float:
        """
        应用结束时间修正逻辑（检查词间空隙、倒二词时长、末尾词时长）。
        """
        if not segment_words:
            return raw_end_time

        duration_threshold = 0.5  # 异常时长阈值 (0.5s)
        gap_threshold = 0.6       # 异常空隙阈值 (0.6s)
        correction_padding = 0.3  # 修正时使用的"留白" (0.3s)
        
        # 检查1 (空隙优先): 检查倒数第二个词和最后一个词之间的“空隙”
        if len(segment_words) > 1:
            last_word = segment_words[-1]
            word_before_last = segment_words[-2]
            
            gap_duration = last_word.start_time - word_before_last.end_time
            
            if gap_duration > gap_threshold:
                self.log(f"字幕时间优化: 修正词间异常空隙 ({gap_duration:.2f}s)")
                # 以"倒二词"的 *开始* 时间为基准
                new_end_time = word_before_last.start_time + correction_padding
                
                # 安全检查
                if new_end_time < segment_start_time:
                    return segment_start_time + correction_padding
                return new_end_time # 命中规则，立即返回

        # 检查2 (倒二词时长): (仅在“空隙”干净时才执行此检查)
        if len(segment_words) > 1:
            word_before_last = segment_words[-2]
            word_before_last_duration = word_before_last.end_time - word_before_last.start_time
            
            if word_before_last_duration > duration_threshold:
                self.log(f"字幕时间优化: 修正异常词时长 ({word_before_last_duration:.2f}s)")
                new_end_time = word_before_last.start_time + correction_padding
                
                # 安全检查
                if new_end_time < segment_start_time:
                    return segment_start_time + correction_padding
                return new_end_time # 命中规则，立即返回

        # 检查3 (末尾词时长): (仅在“空隙”和“倒二词”都干净时才执行此检查)
        last_word = segment_words[-1]
        last_word_duration = last_word.end_time - last_word.start_time
        
        if last_word_duration > duration_threshold:
            self.log(f"字幕时间优化: 修正末尾词异常时长 ({last_word_duration:.2f}s)")
            new_end_time = last_word.start_time + correction_padding

            # 安全检查
            if new_end_time < segment_start_time:
                return segment_start_time + correction_padding
            return new_end_time # 命中规则

        # 如果所有检查都通过，返回原始时间
        return raw_end_time
    # --- 辅助函数 结束 ---

    def split_long_sentence(self, sentence_text: str, sentence_words: List[TimestampedWord],
                            original_start_time: float, original_end_time: float
                           ) -> List[SubtitleEntry]:
        # 检查是否为括号内容，如果是则不分割
        if self._is_bracketed_content(sentence_text.strip()):
            self.log(f"   检测到括号内容，跳过长句分割: \"{sentence_text}\"")
            entry = SubtitleEntry(0, original_start_time, original_end_time, sentence_text, sentence_words)
            if entry.duration < app_config.MIN_DURATION_ABSOLUTE:
                entry.end_time = entry.start_time + app_config.MIN_DURATION_ABSOLUTE
            if entry.duration > self.max_duration or len(sentence_text) > self.max_chars_per_line:
                entry.is_intentionally_oversized = True
            return [entry]

        if not sentence_words:
            if sentence_text.strip():
                self.log(f"警告: split_long_sentence 收到空词列表但有文本: \"{sentence_text}\"。将尝试创建单个条目。")
                entry = SubtitleEntry(0, original_start_time, original_end_time, sentence_text, [])
                if entry.duration < app_config.MIN_DURATION_ABSOLUTE: entry.end_time = entry.start_time + app_config.MIN_DURATION_ABSOLUTE
                if entry.duration > self.max_duration or len(sentence_text) > self.max_chars_per_line:
                    entry.is_intentionally_oversized = True
                return [entry]
            return []
        if len(sentence_words) <= 1:
            entry_to_return = SubtitleEntry(0, original_start_time, original_end_time, sentence_text, sentence_words)
            if entry_to_return.duration < app_config.MIN_DURATION_ABSOLUTE:
                entry_to_return.end_time = entry_to_return.start_time + app_config.MIN_DURATION_ABSOLUTE
            if entry_to_return.duration > self.max_duration or len(sentence_text) > self.max_chars_per_line:
                 entry_to_return.is_intentionally_oversized = True
            return [entry_to_return]
        entries: List[SubtitleEntry] = []
        words_to_process = list(sentence_words)
        while words_to_process:
            current_segment_text = "".join([w.text for w in words_to_process])
            if not words_to_process: break
            current_segment_start_time = words_to_process[0].start_time
            current_segment_end_time = words_to_process[-1].end_time
            current_segment_duration = current_segment_end_time - current_segment_start_time
            current_segment_len_chars = len(current_segment_text)
            if current_segment_duration <= self.max_duration and current_segment_len_chars <= self.max_chars_per_line:
                
                # 应用结束时间修正 (最后一段)
                final_seg_end_time = self._apply_end_time_correction(words_to_process, current_segment_end_time, current_segment_start_time)

                # (重新计算修正后的时长)
                current_segment_duration_corrected = final_seg_end_time - current_segment_start_time

                if current_segment_duration_corrected < self.min_duration_target:
                    final_seg_end_time = current_segment_start_time + self.min_duration_target
                if current_segment_duration_corrected < app_config.MIN_DURATION_ABSOLUTE:
                    final_seg_end_time = current_segment_start_time + app_config.MIN_DURATION_ABSOLUTE
                
                # (已注释掉) 确保修正后的时间不会被原始时间覆盖
                # final_seg_end_time = max(final_seg_end_time, current_segment_end_time) 

                final_seg_end_time = max(final_seg_end_time, current_segment_start_time + 0.001)
                entries.append(SubtitleEntry(0, current_segment_start_time, final_seg_end_time, current_segment_text, list(words_to_process)))
                break 
            potential_split_indices_by_priority = {'final': [], 'ellipsis': [], 'comma': []}
            num_words_in_current_chunk = len(words_to_process)
            for i in range(num_words_in_current_chunk -1):
                word_obj_in_loop = words_to_process[i]
                word_text_in_loop = word_obj_in_loop.text
                if self.check_word_has_punctuation(word_text_in_loop, app_config.FINAL_PUNCTUATION):
                    potential_split_indices_by_priority['final'].append(i)
                elif self.check_word_has_punctuation(word_text_in_loop, app_config.ELLIPSIS_PUNCTUATION):
                    potential_split_indices_by_priority['ellipsis'].append(i)
                elif self.check_word_has_punctuation(word_text_in_loop, app_config.COMMA_PUNCTUATION):
                    potential_split_indices_by_priority['comma'].append(i)
            chosen_priority_indices: Optional[List[int]] = None
            if potential_split_indices_by_priority['final']: chosen_priority_indices = potential_split_indices_by_priority['final']
            elif potential_split_indices_by_priority['ellipsis']: chosen_priority_indices = potential_split_indices_by_priority['ellipsis']
            elif potential_split_indices_by_priority['comma']: chosen_priority_indices = potential_split_indices_by_priority['comma']
            valid_split_points_info: List[tuple[int, int, float]] = []
            if chosen_priority_indices:
                for idx in chosen_priority_indices:
                    first_segment_words = words_to_process[:idx + 1]
                    if not first_segment_words: continue
                    first_segment_start_time = first_segment_words[0].start_time
                    first_segment_end_time = first_segment_words[-1].end_time
                    
                    # 应用结束时间修正 (检查分割点)
                    first_segment_end_time = self._apply_end_time_correction(first_segment_words, first_segment_end_time, first_segment_start_time)

                    first_segment_duration = first_segment_end_time - first_segment_start_time
                    first_segment_char_len = len("".join(w.text for w in first_segment_words))
                    if first_segment_duration >= self.min_duration_target and \
                       first_segment_duration <= self.max_duration and \
                       first_segment_char_len <= self.max_chars_per_line:
                        valid_split_points_info.append((idx, first_segment_char_len, first_segment_duration))
            best_split_index = -1
            if valid_split_points_info:
                target_char_len_half = current_segment_len_chars / 2.0
                best_split_point_data = min(valid_split_points_info, key=lambda p_info: abs(p_info[1] - target_char_len_half))
                best_split_index = best_split_point_data[0]
            if best_split_index != -1:
                words_for_this_sub_entry = words_to_process[:best_split_index + 1]
                sub_text = "".join([w.text for w in words_for_this_sub_entry])
                sub_start_time = words_for_this_sub_entry[0].start_time
                sub_end_time = words_for_this_sub_entry[-1].end_time 
                
                # 应用结束时间修正 (创建分割条目)
                sub_end_time = self._apply_end_time_correction(words_for_this_sub_entry, sub_end_time, sub_start_time)

                # (重新计算修正后的时长)
                sub_duration_corrected = sub_end_time - sub_start_time

                if (sub_duration_corrected) < self.min_duration_target: sub_end_time = sub_start_time + self.min_duration_target
                if (sub_duration_corrected) < app_config.MIN_DURATION_ABSOLUTE: sub_end_time = sub_start_time + app_config.MIN_DURATION_ABSOLUTE
                
                # (已注释掉) 确保修正后的时间不会被原始时间覆盖
                # sub_end_time = max(sub_end_time, words_for_this_sub_entry[-1].end_time) 

                sub_end_time = max(sub_end_time, sub_start_time + 0.001)
                entries.append(SubtitleEntry(0, sub_start_time, sub_end_time, sub_text, words_used=words_for_this_sub_entry))
                words_to_process = words_to_process[best_split_index + 1:]
            else: 
                self.log(f"警告: 无法在片段 '{current_segment_text[:50]}...' 中找到满足所有条件的分割点。将其作为一个（可能超限的）条目处理。")
                final_seg_end_time_fallback = current_segment_end_time
                
                # 应用结束时间修正 (无法分割的回退)
                final_seg_end_time_fallback = self._apply_end_time_correction(words_to_process, final_seg_end_time_fallback, current_segment_start_time)

                # (重新计算修正后的时长)
                current_segment_duration_corrected = final_seg_end_time_fallback - current_segment_start_time

                if current_segment_duration_corrected < self.min_duration_target: final_seg_end_time_fallback = current_segment_start_time + self.min_duration_target
                if current_segment_duration_corrected < app_config.MIN_DURATION_ABSOLUTE: final_seg_end_time_fallback = current_segment_start_time + app_config.MIN_DURATION_ABSOLUTE
                
                # (已注释掉) 确保修正后的时间不会被原始时间覆盖
                # final_seg_end_time_fallback = max(final_seg_end_time_fallback, current_segment_end_time)
                
                final_seg_end_time_fallback = max(final_seg_end_time_fallback, current_segment_start_time + 0.001)
                entry = SubtitleEntry(0, current_segment_start_time, final_seg_end_time_fallback, current_segment_text, list(words_to_process))
                entry.is_intentionally_oversized = True 
                if entry.duration > self.max_duration or len(entry.text) > self.max_chars_per_line:
                     self.log(f"   (确认仍超限) 时长 {entry.duration:.2f}s ({self.max_duration}s限制), 字符 {len(entry.text)} ({self.max_chars_per_line}限制)")
                entries.append(entry)
                break 
            if not words_to_process: break 
        return entries

    # --- 智能合并算法辅助函数 (移植自 Scribe2SRT) ---
    def _is_cjk(self, text: str) -> bool:
        """检查文本是否包含 CJK (中日韩) 字符"""
        for char in text:
            if '\u4e00' <= char <= '\u9fff' or \
               '\u3040' <= char <= '\u309f' or \
               '\u30a0' <= char <= '\u30ff' or \
               '\uac00' <= char <= '\ud7af':
                return True
        return False

    def _calculate_cps(self, text: str, duration: float) -> float:
        """计算每秒字符数 (CPS)"""
        if duration <= 0: return 999.0
        # 去除空白字符计算实际字符数
        char_count = len(re.sub(r'\s+', '', text))
        return char_count / duration

    def _can_merge_entries(self, entry1: SubtitleEntry, entry2: SubtitleEntry) -> tuple[bool, str]:
        """检查两个条目是否可以合并"""
        # 1. 检查音频事件 (Audio Events)
        # 任何包含音频事件的条目都不应合并
        is_evt1 = self._is_bracketed_content(entry1.text) or (self._is_audio_event_words(entry1.words_used) if entry1.words_used else False)
        is_evt2 = self._is_bracketed_content(entry2.text) or (self._is_audio_event_words(entry2.words_used) if entry2.words_used else False)
        if is_evt1 or is_evt2: return False, "包含音频事件"

        # 2. 检查时间间隔 (Gap)
        gap = entry2.start_time - entry1.end_time
        if gap > 2.0: return False, "时间间隔过大"
        
        # 3. 检查合并后的时长 (Duration)
        merged_duration = entry2.end_time - entry1.start_time
        if merged_duration > self.max_duration: return False, "合并后时长过长"

        # 4. 检查文本长度和 CPS
        # 确定分隔符：如果是两个 CJK 文本，中间不加空格
        sep = "" if (self._is_cjk(entry1.text) and self._is_cjk(entry2.text)) else " "
        merged_text = entry1.text + sep + entry2.text
        
        if len(merged_text) > self.max_chars_per_line: return False, "合并后文本过长"
        
        cps = self._calculate_cps(merged_text, merged_duration)
        # 动态 CPS 限制：CJK 稍微严格一点，Latin 宽松一点
        max_cps = 13.0 if self._is_cjk(merged_text) else 18.0 
        if cps > max_cps: return False, f"合并后语速过快 (CPS: {cps:.1f})"

        return True, "OK"

    def _calculate_merge_benefit(self, entry1: SubtitleEntry, entry2: SubtitleEntry) -> float:
        """计算合并收益分数 (分数越高越值得合并)"""
        score = 0.0
        
        # 1. 时长收益：合并过短的条目收益很高
        if entry1.duration < self.min_duration_target:
            score += (self.min_duration_target - entry1.duration) * 20
        if entry2.duration < self.min_duration_target:
            score += (self.min_duration_target - entry2.duration) * 20
            
        # 2. 间隔收益：间隔越小越好
        gap = entry2.start_time - entry1.end_time
        if gap < 0.3:
            score += (0.3 - gap) * 10
        elif gap < 0.5:
            score += (0.5 - gap) * 5
            
        # 3. 文本长度收益：合并极短文本收益较高
        if len(entry1.text) < 5: score += 5
        if len(entry2.text) < 5: score += 5
        
        return score

    def _merge_two_entries(self, entry1: SubtitleEntry, entry2: SubtitleEntry) -> SubtitleEntry:
        """执行合并操作"""
        # 智能处理空格
        sep = "" if (self._is_cjk(entry1.text) and self._is_cjk(entry2.text)) else " "
        merged_text = entry1.text + sep + entry2.text
        
        merged_words = (entry1.words_used or []) + (entry2.words_used or [])
        merged_ratio = min(entry1.alignment_ratio, entry2.alignment_ratio)
        
        return SubtitleEntry(0, entry1.start_time, entry2.end_time, merged_text, merged_words, merged_ratio)
    # --- 智能合并算法结束 ---

    def process_to_srt(self, parsed_transcription: ParsedTranscription,
                       llm_segments_text: List[str]
                      ) -> Optional[str]:
        self.log("--- 开始对齐 LLM 片段 (SrtProcessor) ---")
        intermediate_entries: List[SubtitleEntry] = []
        word_search_start_index = 0
        unaligned_segments: List[str] = []
        all_parsed_words = parsed_transcription.words
        if not llm_segments_text: self.log("错误：LLM 未返回任何分割片段。"); return None
        if not all_parsed_words: self.log("错误：解析后的词列表为空，无法进行对齐。"); return None

        
        total_llm_segments = len(llm_segments_text)
        WEIGHT_ALIGN = 40; WEIGHT_MERGE = 30; WEIGHT_FORMAT = 30
        completed_steps_phase1 = 0
        self.log("SRT阶段1: 对齐LLM片段...")
        for i, text_seg_from_llm in enumerate(llm_segments_text):
            if not self._is_worker_running(): self.log("任务被用户中断(对齐阶段)。"); return None
            self.log(f"   对齐LLM片段 {i+1}/{total_llm_segments}: \"{text_seg_from_llm[:30]}...\"")
            matched_words, next_search_idx, match_ratio = self.get_segment_words_fuzzy(text_seg_from_llm, all_parsed_words, word_search_start_index)
            if not matched_words or match_ratio == 0:
                unaligned_segments.append(text_seg_from_llm)
                completed_steps_phase1 += 1
                self._emit_srt_progress(int( (completed_steps_phase1 / total_llm_segments) * WEIGHT_ALIGN ), 100)
                continue

            
            word_search_start_index = next_search_idx
            first_actual_word_index = -1
            for idx_fw, word_obj_fw in enumerate(matched_words):
                if word_obj_fw.text.strip(): first_actual_word_index = idx_fw; break
            last_actual_word_index = -1
            for idx_bw in range(len(matched_words) - 1, -1, -1):
                if matched_words[idx_bw].text.strip(): last_actual_word_index = idx_bw; break
            entry_text_from_llm = text_seg_from_llm.strip()
            actual_words_for_entry: List[TimestampedWord]
            if first_actual_word_index != -1 and last_actual_word_index != -1 :
                entry_start_time = matched_words[first_actual_word_index].start_time
                entry_end_time = matched_words[last_actual_word_index].end_time
                actual_words_for_entry = matched_words[first_actual_word_index : last_actual_word_index+1]
                if not actual_words_for_entry:
                    self.log(f"警告: 修正后的词列表为空，LLM片段 \"{entry_text_from_llm[:30]}...\"。将使用原始匹配边界。")
                    entry_start_time = matched_words[0].start_time; entry_end_time = matched_words[-1].end_time
                    actual_words_for_entry = matched_words
            else:
                self.log(f"警告: LLM片段 \"{entry_text_from_llm[:30]}...\" 匹配到的所有ASR词元均为空或空格。将使用原始匹配边界。")
                entry_start_time = matched_words[0].start_time; entry_end_time = matched_words[-1].end_time
                actual_words_for_entry = matched_words
            
            entry_duration = max(0.001, entry_end_time - entry_start_time)
            text_len = len(entry_text_from_llm)
            is_audio_event = self._is_audio_event_words(actual_words_for_entry) if actual_words_for_entry else False

            # 应用结束时间修正 (主流程)
            final_audio_event_end_time = entry_end_time
            if is_audio_event:
                # 音频事件：保持原始结束时间，不应用时间修正
                self.log(f"   检测到音频事件，保持原始时长: \"{entry_text_from_llm}\"")
            else:
                # 非音频事件：应用正常的时间修正
                entry_end_time = self._apply_end_time_correction(actual_words_for_entry, entry_end_time, entry_start_time)
                final_audio_event_end_time = entry_end_time

            if is_audio_event:
                # 音频事件：使用修正后的时间（可能包含向前延长），但不向后延长
                audio_event_text_content = "".join([w.text for w in actual_words_for_entry])
                intermediate_entries.append(SubtitleEntry(0, entry_start_time, final_audio_event_end_time, audio_event_text_content, actual_words_for_entry, match_ratio))
            elif entry_duration > self.max_duration or text_len > self.max_chars_per_line:
                self.log(f"   片段超限，需分割: \"{entry_text_from_llm[:50]}...\" (时长: {entry_duration:.2f}s, 字符: {text_len})")
                # 此处 entry_end_time 已经是被修正过的了
                split_sub_entries = self.split_long_sentence(entry_text_from_llm, actual_words_for_entry, entry_start_time, entry_end_time)
                for sub_entry in split_sub_entries: sub_entry.alignment_ratio = match_ratio
                intermediate_entries.extend(split_sub_entries)
            elif entry_duration < self.min_duration_target :
                # 检查是否为括号内容，如果是则不进行时长扩展
                is_bracketed = self._is_bracketed_content(entry_text_from_llm)

                if is_bracketed:
                    # 括号内容保持原始时长，不强制扩展
                    self.log(f"   检测到括号内容，保持原始时长: \"{entry_text_from_llm}\" ({entry_duration:.2f}s)")
                    final_short_entry_end_time = final_audio_event_end_time if is_audio_event else entry_end_time
                else:
                    # 非括号内容的正常时长扩展逻辑
                    final_short_entry_end_time = entry_start_time + self.min_duration_target
                    if entry_duration < app_config.MIN_DURATION_ABSOLUTE: final_short_entry_end_time = entry_start_time + app_config.MIN_DURATION_ABSOLUTE
                    original_end_of_last_actual_word = actual_words_for_entry[-1].end_time if actual_words_for_entry else entry_start_time
                    max_allowed_extension = original_end_of_last_actual_word + 0.5
                    final_short_entry_end_time = min(final_short_entry_end_time, max_allowed_extension)
                    final_short_entry_end_time = max(final_short_entry_end_time, entry_end_time) # entry_end_time 可能是被修正过的
                    final_short_entry_end_time = max(final_short_entry_end_time, entry_start_time + 0.001)

                intermediate_entries.append(SubtitleEntry(0, entry_start_time, final_short_entry_end_time, entry_text_from_llm, actual_words_for_entry, match_ratio))
            else:
                # 此处 entry_end_time 已经是被修正过的了
                intermediate_entries.append(SubtitleEntry(0, entry_start_time, entry_end_time, entry_text_from_llm, actual_words_for_entry, match_ratio))
            completed_steps_phase1 += 1
            self._emit_srt_progress(int( (completed_steps_phase1 / total_llm_segments) * WEIGHT_ALIGN ), 100)
        self.log("--- LLM片段对齐结束 ---")
        if unaligned_segments:
            self.log(f"\\n--- 以下 {len(unaligned_segments)} 个LLM片段未能成功对齐，已跳过 ---")
            for seg_idx, seg_text in enumerate(unaligned_segments): self.log(f"- 片段 {seg_idx+1}: \"{seg_text}\"")
            self.log("----------------------------------------\\n")
        if not intermediate_entries: self.log("错误：对齐后没有生成任何有效的字幕条目。"); return None
        intermediate_entries.sort(key=lambda e: e.start_time)
        
        # --- Phase 2: 智能合并 (Modified) ---
        self.log("SRT阶段2: 合并调整字幕条目 (智能收益算法)...")
        merged_entries: List[SubtitleEntry] = []
        idx_merge = 0
        total_intermediate_entries = len(intermediate_entries)
        
        while idx_merge < total_intermediate_entries:
            if not self._is_worker_running(): self.log("任务被用户中断(合并阶段)。"); return None
            
            current_entry = intermediate_entries[idx_merge]
            merged_this_iteration = False
            
            # 尝试与下一条合并
            if idx_merge + 1 < len(intermediate_entries):
                next_entry = intermediate_entries[idx_merge+1]
                
                # 检查是否满足合并的基本硬性条件
                can_merge, reason = self._can_merge_entries(current_entry, next_entry)
                
                if can_merge:
                    # 计算合并收益
                    benefit = self._calculate_merge_benefit(current_entry, next_entry)
                    
                    # 只有收益超过阈值才合并 (Scribe2SRT 默认阈值 5.0)
                    if benefit > 5.0:
                        self.log(f"   合并字幕 (收益 {benefit:.1f}): \"{current_entry.text[:15]}...\" + \"{next_entry.text[:15]}...\"")
                        merged_entry = self._merge_two_entries(current_entry, next_entry)
                        merged_entries.append(merged_entry)
                        idx_merge += 2
                        merged_this_iteration = True
                    else:
                        pass

            if not merged_this_iteration:
                merged_entries.append(current_entry)
                idx_merge += 1
                
            current_phase2_progress_component = int(((idx_merge) / total_intermediate_entries if total_intermediate_entries > 0 else 1) * WEIGHT_MERGE)
            self._emit_srt_progress(WEIGHT_ALIGN + current_phase2_progress_component, 100)
        # --- End Phase 2 ---

        self.log(f"--- 合并调整后得到 {len(merged_entries)} 个字幕条目，开始最终格式化 ---")
        self.log("SRT阶段3: 最终格式化字幕...")
        final_srt_formatted_list: List[str] = []
        last_processed_entry_object: Optional[SubtitleEntry] = None
        subtitle_index = 1
        total_merged_final_entries = len(merged_entries)
        for entry_idx, current_entry in enumerate(merged_entries):
            if not self._is_worker_running(): self.log("任务被用户中断(最终格式化阶段)。"); return None
            self.log(f"   格式化条目 {entry_idx+1}/{total_merged_final_entries}: \"{current_entry.text[:30]}...\"")
            if last_processed_entry_object is not None:

                # 检测并修正时间重叠
                raw_gap = current_entry.start_time - last_processed_entry_object.end_time
                if raw_gap < -0.01:  # 检测到负时间（重叠）
                    self.log(f"字幕时间重叠修正: 调整重叠时间 {raw_gap:.3f}s")
                    # 将当前条目的开始时间调整为上一条目结束时间 + 最小间隔
                    new_start_time = last_processed_entry_object.end_time + 0.01  # 最小间隔10ms
                    if new_start_time < current_entry.end_time:
                        current_entry.start_time = new_start_time

                # 应用开始时间修正 (提前0.25s)
                # 对于音频事件，不应用修正
                current_is_audio_event = self._is_bracketed_content(current_entry.text)
                if current_is_audio_event:
                    self.log(f"   检测到音频事件，跳过开始时间修正")
                elif raw_gap > 0.5:
                    self.log(f"字幕时间优化: 检测到较大时间间隙 ({raw_gap:.2f}s)")
                    new_start_time = current_entry.start_time - 0.25
                    # 安全检查: 确保提前后不会与上一句重叠
                    if new_start_time > last_processed_entry_object.end_time:
                        self.log(f"字幕时间优化: 提前开始时间以减少间隙")
                        current_entry.start_time = new_start_time
                    else:
                        self.log(f"时间优化跳过: 会与上一句重叠")
                
                # (继续执行原有的 100ms 间隙逻辑)
                # 检查当前条目是否为音频事件，如果是则豁免最小间距要求
                current_is_audio_event = self._is_bracketed_content(current_entry.text)
                last_is_audio_event = self._is_bracketed_content(last_processed_entry_object.text)

                gap_seconds = self.default_gap_ms / 1000.0

                # 如果任一条目是音频事件，豁免最小间距检查
                if current_is_audio_event or last_is_audio_event:
                    self.log(f"   检测到音频事件内容，豁免最小间距检查")
                elif current_entry.start_time < last_processed_entry_object.end_time + gap_seconds:
                    # 修正策略：调整当前条目的开始时间，而不是修改前一个条目的结束时间
                    new_current_start_time = last_processed_entry_object.end_time + gap_seconds
                    # 确保当前条目有足够的最小时长
                    min_current_duration = app_config.MIN_DURATION_ABSOLUTE
                    if new_current_start_time + min_current_duration <= current_entry.end_time:
                        self.log(f"字幕时间优化: 调整以保持最小间距")
                        current_entry.start_time = new_current_start_time
                    if final_srt_formatted_list: 
                        final_srt_formatted_list[-1] = last_processed_entry_object.to_srt_format(self)
            current_duration = current_entry.duration 
            min_duration_to_apply_val: Optional[float] = None
            entry_is_audio_event = False
            if current_entry.words_used: entry_is_audio_event = any(not w.text.strip() or getattr(w, 'type', 'word') == 'audio_event' or re.match(r"^\(.*\)$|^（.*）$", w.text.strip()) for w in current_entry.words_used)
            if not current_entry.is_intentionally_oversized and not entry_is_audio_event:
                if current_duration < self.min_duration_target: min_duration_to_apply_val = self.min_duration_target
                if current_duration < app_config.MIN_DURATION_ABSOLUTE: min_duration_to_apply_val = app_config.MIN_DURATION_ABSOLUTE 
            if min_duration_to_apply_val is not None:
                current_entry.end_time = max(current_entry.end_time, current_entry.start_time + min_duration_to_apply_val)
            if not current_entry.is_intentionally_oversized and current_entry.duration > self.max_duration:
                self.log(f"字幕 \"{current_entry.text[:30]}...\" 时长 {current_duration:.2f}s 超出最大值 {self.max_duration}s，将被截断。")
                current_entry.end_time = current_entry.start_time + self.max_duration
            if current_entry.end_time <= current_entry.start_time: 
                 current_entry.end_time = current_entry.start_time + 0.001
            
            current_entry.index = subtitle_index
            final_srt_formatted_list.append(current_entry.to_srt_format(self))
            last_processed_entry_object = current_entry; subtitle_index += 1
            current_phase3_progress_component = int(((entry_idx + 1) / total_merged_final_entries if total_merged_final_entries > 0 else 1) * WEIGHT_FORMAT)
            self._emit_srt_progress(WEIGHT_ALIGN + WEIGHT_MERGE + current_phase3_progress_component, 100)
        self.log("--- SRT 内容生成和格式化完成 ---")
        return "".join(final_srt_formatted_list).strip()