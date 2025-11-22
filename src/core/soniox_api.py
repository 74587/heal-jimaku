#!/usr/bin/env python3
"""
Soniox Speech-to-Text API 客户端
支持异步转录、Context优化、多语言识别等功能
"""

import os
import json
import time
import requests
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class SonioxTranscriptionConfig:
    """Soniox转录配置"""
    api_key: str
    language_hints: List[str] = None
    enable_speaker_diarization: bool = True
    enable_language_identification: bool = True
    context_terms: List[str] = None
    context_text: str = None
    context_general: List[Dict[str, str]] = None
    model: str = "stt-async-v3"

    def __post_init__(self):
        if self.language_hints is None:
            self.language_hints = []
        if self.context_terms is None:
            self.context_terms = []
        if self.context_general is None:
            self.context_general = []

class SonioxClient:
    """Soniox Speech-to-Text API 客户端"""

    SONIOX_API_BASE_URL = "https://api.soniox.com"

    def __init__(self, signals_forwarder: Optional[Any] = None):
        self._signals = signals_forwarder
        self._session = requests.Session()

    def _emit_log(self, message: str, level: str = "info"):
        """发射日志信号 - 保持与现有代码一致的日志格式"""
        if self._signals:
            if hasattr(self._signals, 'log_signal'):
                self._signals.log_signal.emit(f"[Soniox API] {message}")
        else:
            print(f"[Soniox API] {message}")

    def _emit_progress(self, current: int, total: int, message: str = ""):
        """发射进度信号 - 保持与现有代码一致的进度格式"""
        if self._signals:
            if hasattr(self._signals, 'progress_signal'):
                self._signals.progress_signal.emit(current, total, message)

    def get_audio_info(self, audio_file_path: str) -> Tuple[Optional[float], Optional[int]]:
        """获取音频文件信息 - 复用现有的音频信息获取逻辑"""
        try:
            file_size = os.path.getsize(audio_file_path)

            # 尝试使用mutagen获取音频时长
            try:
                from mutagen import File as MutagenFile
                audio_file = MutagenFile(audio_file_path)
                if audio_file is not None and hasattr(audio_file, 'info'):
                    duration = audio_file.info.length
                    return duration, file_size
            except Exception as e:
                logger.warning(f"无法使用mutagen获取音频时长: {e}")

            return None, file_size
        except Exception as e:
            logger.error(f"获取音频信息失败: {e}")
            return None, None

    def _build_transcription_config(self, config: SonioxTranscriptionConfig,
                                   file_id: Optional[str] = None,
                                   audio_url: Optional[str] = None) -> Dict[str, Any]:
        """构建转录请求配置"""
        transcription_config = {
            "model": config.model,
            "enable_speaker_diarization": config.enable_speaker_diarization,
            "enable_language_identification": config.enable_language_identification,
        }

        # 添加音频源
        if file_id:
            transcription_config["file_id"] = file_id
        elif audio_url:
            transcription_config["audio_url"] = audio_url

        # 添加语言提示
        if config.language_hints:
            transcription_config["language_hints"] = config.language_hints

        # 构建上下文 - 按照Soniox v3 API的格式要求
        context = {}

        # General上下文
        if config.context_general:
            context["general"] = config.context_general

        # Terms上下文 - 专有名词列表
        if config.context_terms:
            context["terms"] = config.context_terms

        # Text上下文 - 剧情简介或背景文本
        if config.context_text and config.context_text.strip():
            context["text"] = config.context_text.strip()

        if context:
            transcription_config["context"] = context

        return transcription_config

    def upload_audio_file(self, audio_file_path: str, api_key: str) -> Optional[str]:
        """上传音频文件到Soniox"""
        try:
            self._emit_log("开始上传音频文件到Soniox...")
            self._emit_progress(1, 4, "上传音频文件")

            upload_url = f"{self.SONIOX_API_BASE_URL}/v1/files"
            headers = {"Authorization": f"Bearer {api_key}"}

            file_size = os.path.getsize(audio_file_path)
            self._emit_log(f"文件大小: {file_size / (1024*1024):.2f} MB")

            with open(audio_file_path, "rb") as f:
                files = {"file": f}
                response = self._session.post(upload_url, headers=headers, files=files)

            self._emit_progress(2, 4, "解析上传响应")

            if response.status_code != 200:
                error_msg = f"上传失败: HTTP {response.status_code} - {response.text}"
                self._emit_log(error_msg)
                return None

            result = response.json()
            file_id = result.get("id")

            if file_id:
                self._emit_log(f"文件上传成功，文件ID: {file_id}")
                self._emit_progress(3, 4, "上传完成")
                return file_id
            else:
                self._emit_log("上传响应中未找到文件ID")
                return None

        except Exception as e:
            self._emit_log(f"上传音频文件异常: {e}")
            return None

    def create_transcription(self, config: SonioxTranscriptionConfig,
                           file_id: Optional[str] = None,
                           audio_url: Optional[str] = None) -> Optional[str]:
        """创建转录任务"""
        try:
            self._emit_log("创建Soniox转录任务...")

            create_url = f"{self.SONIOX_API_BASE_URL}/v1/transcriptions"
            headers = {
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json"
            }

            # 构建转录配置
            transcription_config = self._build_transcription_config(
                config, file_id, audio_url
            )

            self._emit_log(f"使用模型: {config.model}")
            if config.language_hints:
                self._emit_log(f"语言提示: {', '.join(config.language_hints)}")
            if config.context_terms or config.context_text:
                self._emit_log("已配置上下文优化")

            response = self._session.post(
                create_url,
                headers=headers,
                json=transcription_config
            )

            if response.status_code != 200:
                error_msg = f"创建转录失败: HTTP {response.status_code} - {response.text}"
                self._emit_log(error_msg)
                return None

            result = response.json()
            transcription_id = result.get("id")

            if transcription_id:
                self._emit_log(f"转录任务创建成功，ID: {transcription_id}")
                return transcription_id
            else:
                self._emit_log("创建响应中未找到转录ID")
                return None

        except Exception as e:
            self._emit_log(f"创建转录任务异常: {e}")
            return None

    def poll_transcription_result(self, transcription_id: str, api_key: str,
                                 timeout_seconds: int = 1800) -> Optional[Dict]:
        """轮询转录结果"""
        try:
            self._emit_log("开始轮询Soniox转录结果...")
            self._emit_progress(4, 4, "等待转录完成")

            get_url = f"{self.SONIOX_API_BASE_URL}/v1/transcriptions/{transcription_id}"
            headers = {"Authorization": f"Bearer {api_key}"}

            start_time = time.time()
            poll_interval = 5  # 5秒轮询间隔

            while True:
                elapsed_time = time.time() - start_time

                if elapsed_time > timeout_seconds:
                    self._emit_log(f"转录超时 ({timeout_seconds}秒)")
                    return None

                response = self._session.get(get_url, headers=headers)

                if response.status_code != 200:
                    error_msg = f"获取转录状态失败: HTTP {response.status_code}"
                    self._emit_log(error_msg)
                    return None

                result = response.json()
                status = result.get("status")

                self._emit_log(f"转录状态: {status} (已等待 {elapsed_time:.0f}秒)")

                if status == "completed":
                    self._emit_log("Soniox转录完成！")
                    return result
                elif status == "error":
                    error_message = result.get("error_message", "未知错误")
                    self._emit_log(f"转录失败: {error_message}")
                    return None
                elif status in ["queued", "processing"]:
                    # 继续等待
                    time.sleep(poll_interval)
                else:
                    self._emit_log(f"未知状态: {status}")
                    time.sleep(poll_interval)

        except Exception as e:
            self._emit_log(f"轮询转录结果异常: {e}")
            return None

    def transcribe_audio_file(self, audio_file_path: str,
                            config: SonioxTranscriptionConfig) -> Optional[Dict]:
        """完整的音频文件转录流程"""
        try:
            # 1. 获取音频信息
            duration, file_size = self.get_audio_info(audio_file_path)
            if duration:
                self._emit_log(f"音频时长: {duration:.2f}秒")

            # 2. 上传文件
            file_id = self.upload_audio_file(audio_file_path, config.api_key)
            if not file_id:
                return None

            # 3. 创建转录任务
            transcription_id = self.create_transcription(config, file_id=file_id)
            if not transcription_id:
                return None

            # 4. 轮询结果
            result = self.poll_transcription_result(transcription_id, config.api_key)
            if result:
                # 添加元数据，保持与现有代码一致的数据结构
                result["soniox_metadata"] = {
                    "file_id": file_id,
                    "transcription_id": transcription_id,
                    "audio_duration": duration,
                    "audio_file_size": file_size,
                    "config": {
                        "model": config.model,
                        "language_hints": config.language_hints,
                        "enable_speaker_diarization": config.enable_speaker_diarization,
                        "has_context": bool(config.context_terms or config.context_text or config.context_general)
                    }
                }

            return result

        except Exception as e:
            self._emit_log(f"音频转录流程异常: {e}")
            return None

    def test_connection(self, api_key: str) -> Tuple[bool, str]:
        """测试API连接 - 保持与现有API测试一致的格式"""
        try:
            self._emit_log("测试Soniox API连接...")

            # 测试获取模型列表
            models_url = f"{self.SONIOX_API_BASE_URL}/v1/models"
            headers = {"Authorization": f"Bearer {api_key}"}

            response = self._session.get(models_url, headers=headers)

            if response.status_code == 200:
                models = response.json().get("models", [])
                stt_models = [m for m in models if "stt" in m.get("model", "").lower()]

                if stt_models:
                    model_names = [m.get("model", "") for m in stt_models]
                    self._emit_log("Soniox API连接成功")
                    return True, f"连接成功！可用模型: {', '.join(model_names[:3])}"
                else:
                    return False, "未找到STT模型"
            else:
                return False, f"连接失败: HTTP {response.status_code} - {response.text}"

        except Exception as e:
            return False, f"测试连接异常: {e}"

# 便捷函数
def create_soniox_config(api_key: str, **kwargs) -> SonioxTranscriptionConfig:
    """创建Soniox转录配置"""
    return SonioxTranscriptionConfig(api_key=api_key, **kwargs)

def transcribe_with_soniox(audio_file_path: str, config: SonioxTranscriptionConfig,
                          signals_forwarder: Optional[Any] = None) -> Optional[Dict]:
    """便捷转录函数"""
    client = SonioxClient(signals_forwarder)
    return client.transcribe_audio_file(audio_file_path, config)