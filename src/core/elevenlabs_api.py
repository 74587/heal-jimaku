"""
ElevenLabs API 客户端模块

提供音频转文字服务的API客户端实现，支持多种音频格式的转录处理。
包含文件信息获取、API请求处理、错误处理等功能。

作者: Heal-Jimaku Project
版本: 1.3.0
"""

import requests
import json
import os
import time
import random
import wave
from typing import Optional, Any, Dict, List, Tuple

from mutagen import File as MutagenFile

# ElevenLabs API 常量定义
ELEVENLABS_STT_API_URL = "https://api.elevenlabs.io/v1/speech-to-text"  # API 端点URL
ELEVENLABS_STT_PARAMS = {
    "allow_unauthenticated": "1"  # 允许未认证访问的参数
}
DEFAULT_STT_MODEL_ID = "scribe_v1"  # 默认使用的转录模型ID
DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918U1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.70 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/124.0.2478.80",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/123.0.2420.97",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 12; SM-A525F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_7_10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 11; CPH2239) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.2277.128",
    "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.0 Safari/537.36"
]

# 默认Accept-Language列表，用于模拟不同语言偏好
DEFAULT_ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7,ja;q=0.6",
    "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,ja;q=0.5",
    "en-GB,en;q=0.9,en-US;q=0.8,de;q=0.7,fr;q=0.6",
    "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
    "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7,fr;q=0.6",
    "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7,es;q=0.6",
    "es-ES,es;q=0.9,en;q=0.8,pt;q=0.7",
    "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7,ja;q=0.6",
    "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7,de;q=0.6",
    "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7,es;q=0.6",
    "en-CA,en;q=0.9,fr-CA;q=0.8",
    "en-AU,en;q=0.9,en-GB;q=0.8",
    "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7,ja;q=0.6",
    "ar-SA,ar;q=0.9,en-US;q=0.8,en;q=0.7",
    "hi-IN,hi;q=0.9,en-US;q=0.8,en;q=0.7",
    "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7,de;q=0.6",
    "sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7,fi;q=0.6",
    "fi-FI,fi;q=0.9,en-US;q=0.8,en;q=0.7,sv;q=0.6",
    "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7,de;q=0.6",
    "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "cs-CZ,cs;q=0.9,en-US;q=0.8,en;q=0.7,sk;q=0.6",
    "hu-HU,hu;q=0.9,en-US;q=0.8,en;q=0.7,de;q=0.6",
    "el-GR,el;q=0.9,en-US;q=0.8,en;q=0.7",
    "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7"
]

class ElevenLabsSTTClient:
    """
    ElevenLabs语音转文本API客户端

    负责与ElevenLabs STT API交互，提供音频转录功能，包括音频信息获取、
    文件上传、转录请求处理和结果解析。支持多语言、说话人分离和音频事件标记。
    """
    def __init__(self, signals_forwarder: Optional[Any] = None):
        self._signals = signals_forwarder

    def _log(self, message: str):
        if self._signals and hasattr(self._signals, 'log_message') and hasattr(self._signals.log_message, 'emit'):
            self._signals.log_message.emit(f"[ElevenLabs API] {message}")
        else:
            print(f"[ElevenLabs API] {message}")

    def _is_worker_running(self) -> bool: # Renamed to avoid confusion with a potential self.is_running
        # Access parent's (ConversionWorker) is_running via signals
        if self._signals and hasattr(self._signals, 'parent') and \
           hasattr(self._signals.parent(), 'is_running'):
            return self._signals.parent().is_running
        return True # Fallback if signals or parent structure is not as expected

    def get_audio_info(self, audio_file_path: str) -> Tuple[Optional[float], Optional[float]]:
        duration_seconds: Optional[float] = None
        file_size_mb: Optional[float] = None
        try:
            if not os.path.exists(audio_file_path):
                self._log(f"错误: 音频文件在 get_audio_info 中未找到: {audio_file_path}")
                return None, None

            file_size_bytes = os.path.getsize(audio_file_path)
            file_size_mb = file_size_bytes / (1024 * 1024)
            
            audio_info = MutagenFile(audio_file_path)
            if audio_info and hasattr(audio_info, 'info') and hasattr(audio_info.info, 'length'):
                duration_seconds = float(audio_info.info.length)
            elif audio_file_path.lower().endswith(".wav"):
                self._log("  Mutagen未能获取WAV时长, 尝试使用wave模块...")
                try:
                    with wave.open(audio_file_path, 'rb') as wf:
                        frames = wf.getnframes()
                        rate = wf.getframerate()
                        if rate > 0:
                            duration_seconds = frames / float(rate)
                        else:
                            self._log("  警告：WAV 文件帧率无效 (wave模块)。")
                except Exception as e_wave:
                    self._log(f"  使用wave模块读取WAV时长错误: {e_wave}")

            if duration_seconds is not None:
                minutes = int(duration_seconds // 60)
                seconds = int(duration_seconds % 60)
                milliseconds = int((duration_seconds - (minutes * 60) - seconds) * 1000)
            else:
                self._log("  警告：未能获取音频时长。")
            
            return duration_seconds, file_size_mb

        except Exception as e:
            self._log(f"  获取音频信息时发生错误: {e}")
            return duration_seconds, file_size_mb

    def transcribe_audio(self,
                         audio_file_path: str,
                         language_code: Optional[str] = None, 
                         num_speakers: Optional[int] = None,
                         tag_audio_events: bool = True) -> Optional[Dict]:
        
        if not self._is_worker_running(): # Check if the main worker task is still running
            self._log("转录任务开始前被取消 (工作线程停止)。")
            return None

        if not os.path.exists(audio_file_path):
            self._log(f"错误：音频文件 '{audio_file_path}' 未找到。")
            return None

        duration, file_size_mb = self.get_audio_info(audio_file_path) 

        headers = {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": random.choice(DEFAULT_ACCEPT_LANGUAGES),
            "origin": "https://elevenlabs.io",
            "referer": "https://elevenlabs.io/",
            "user-agent": random.choice(DEFAULT_USER_AGENTS),
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
        }

        # Diarize is now always True for free tier
        payload_data: Dict[str, Any] = {
            "model_id": DEFAULT_STT_MODEL_ID,
            "tag_audio_events": tag_audio_events,
            "diarize": True 
        }
        
        if language_code and language_code.lower() != "auto":
            payload_data["language_code"] = language_code
        
        if num_speakers is not None and 1 <= num_speakers <= 32:
            payload_data["num_speakers"] = num_speakers
        # If diarize is True (which it always is now) and num_speakers is auto (0 or None),
        # we don't send num_speakers for API's auto detection.

        try:
            with open(audio_file_path, 'rb') as f_audio:
                file_extension = os.path.splitext(audio_file_path)[1].lower()
                mime_type_map = {
                    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".flac": "audio/flac",
                    ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".opus": "audio/opus",
                    ".aac": "audio/aac", ".webm": "audio/webm", ".mp4": "video/mp4",
                    ".mov": "video/quicktime"
                }
                mime_type = mime_type_map.get(file_extension, 'application/octet-stream')
                if mime_type == 'application/octet-stream':
                    self._log(f"  警告：未知的音频文件扩展名 '{file_extension}'，使用通用MIME类型 '{mime_type}'。")
                files_data = { "file": (os.path.basename(audio_file_path), f_audio, mime_type) }

                start_time = time.perf_counter()
                response = requests.post(
                    ELEVENLABS_STT_API_URL,
                    params=ELEVENLABS_STT_PARAMS,
                    headers=headers,
                    data=payload_data,
                    files=files_data,
                    timeout=600 
                )
                end_time = time.perf_counter()
                api_call_duration = end_time - start_time
                self._log(f"ElevenLabs转录请求完成，耗时: {api_call_duration:.2f} 秒")

                if not self._is_worker_running():
                    self._log("API响应后任务已取消 (工作线程停止)。")
                    return None

                response.raise_for_status()
                response_json = response.json()
                self._log("成功从ElevenLabs API获取并解析JSON响应。")
                return response_json

        except requests.exceptions.Timeout:
            self._log(f"错误: ElevenLabs API 请求超时 (10分钟)。")
            return None # Ensure None is returned
        except requests.exceptions.RequestException as e:
            self._log(f"错误: ElevenLabs API 请求过程中发生网络或HTTP错误: {e}")
            if hasattr(e, 'response') and e.response is not None:
                self._log(f"  服务器响应状态码: {e.response.status_code}")
                try:
                    error_content = e.response.json()
                    self._log(f"  服务器错误详情: {error_content}")
                except json.JSONDecodeError:
                    self._log(f"  服务器响应内容 (非JSON): {e.response.text}")
            return None # Ensure None is returned
        except json.JSONDecodeError:
            self._log("错误：无法解析 ElevenLabs API 返回的JSON响应。")
            if 'response' in locals() and hasattr(response, 'text'):
                 self._log(f"  原始响应文本: {response.text[:500]}...")
            return None # Ensure None is returned
        except Exception as e:
            self._log(f"错误: 处理 ElevenLabs API 转录时发生未知错误: {e}")
            import traceback
            self._log(traceback.format_exc())
            return None # Ensure None is returned

        # Fallback, should ideally be caught by specific exceptions above
        return None

