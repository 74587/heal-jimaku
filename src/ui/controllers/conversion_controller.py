"""
转换控制器 - 管理转换任务逻辑和线程管理

该控制器封装了转换任务的业务逻辑，将其与主UI分离，
以提高代码可维护性和可测试性。
"""

import os
from typing import Dict, Any, List
from PyQt6.QtCore import QObject, pyqtSignal, QThread

from ..conversion_worker import ConversionWorker
import config as app_config


class ConversionController(QObject):
    """用于管理SRT转换任务的控制器。"""

    # UI交互信号
    task_started = pyqtSignal()
    task_finished = pyqtSignal(str, bool)
    progress_updated = pyqtSignal(int)
    log_message = pyqtSignal(str)

    def __init__(self, config_manager, elevenlabs_client, srt_processor):
        """
        初始化转换控制器。

        Args:
            config_manager: 主窗口实例，包含配置信息
            elevenlabs_client: ElevenLabs API客户端
            srt_processor: SRT处理器实例
        """
        super().__init__()
        self.config_manager = config_manager
        self.elevenlabs_client = elevenlabs_client
        self.srt_processor = srt_processor

        # 线程管理
        self.worker = None
        self.thread = None

        # 批处理状态
        self._is_batch = False
        self._batch_queue = []
        self._current_batch_index = 0
        self._output_dir = ""
        self._mode = ""
        self._free_params = None
        self._source_format = "elevenlabs"

    def start_single_task(self, input_path: str, output_dir: str, mode: str, free_params: Dict[str, Any] = None, source_format: str = "elevenlabs"):
        """
        启动单文件转换任务。

        Args:
            input_path: 输入文件路径
            output_dir: 输出目录
            mode: 处理模式
            free_params: 免费转录参数
            source_format: JSON文件格式 (elevenlabs, whisper, deepgram, assemblyai)
        """
        self._is_batch = False
        self._start_conversion_worker(input_path, output_dir, mode, free_params, source_format)

    def start_batch_task(self, files: List[str], output_dir: str, mode: str, free_params: Dict[str, Any] = None, source_format: str = "elevenlabs"):
        """
        启动批量转换任务。

        Args:
            files: 要处理的文件列表
            output_dir: 输出目录
            mode: 处理模式
            free_params: 免费转录参数
            source_format: JSON文件格式 (elevenlabs, whisper, deepgram, assemblyai)
        """
        self._is_batch = True
        self._batch_queue = list(files)
        self._current_batch_index = 0
        self._output_dir = output_dir
        self._mode = mode
        self._free_params = free_params
        self._source_format = source_format

        self.log_message.emit(f"开始批量处理 {len(files)} 个文件...")
        self._process_next_batch_item()

    def stop_task(self):
        """停止当前任务。"""
        if self.worker:
            self.worker.stop()
            if self.thread:
                self.thread.quit()
                self.thread.wait()
            self.worker = None
            self.thread = None

    def _process_next_batch_item(self):
        """处理批处理队列中的下一个项目。"""
        if self._current_batch_index >= len(self._batch_queue):
            self.log_message.emit("批量处理完成！")
            self.task_finished.emit("所有文件已成功处理", True)
            return

        current_file = self._batch_queue[self._current_batch_index]
        self.log_message.emit(f"正在处理 ({self._current_batch_index + 1}/{len(self._batch_queue)}): {os.path.basename(current_file)}")

        # 根据模式构建参数
        input_json = ""
        current_free_params = self._free_params.copy() if self._free_params else None

        if self._mode == "free_transcription":
            if current_free_params:
                current_free_params["audio_file_path"] = current_file
        else:
            input_json = current_file

        self._start_conversion_worker(input_json, self._output_dir, self._mode, current_free_params, self._source_format)

    def _start_conversion_worker(self, input_path: str, output_dir: str, mode: str, free_params: Dict[str, Any] = None, source_format: str = "elevenlabs"):
        """
        初始化并启动转换工作线程。

        Args:
            input_path: 输入文件路径
            output_dir: 输出目录
            mode: 处理模式
            free_params: 免费转录参数
            source_format: JSON文件格式
        """
        self.task_started.emit()

        # 获取当前配置的 LLM 参数
        current_profile = app_config.get_current_llm_profile(self.config_manager.config)

        # 将profile格式转换为ConversionWorker期望的格式
        api_base_url = current_profile.get("api_base_url", app_config.DEFAULT_LLM_API_BASE_URL)

        llm_config = {
            app_config.USER_LLM_API_KEY_KEY: current_profile.get("api_key", app_config.DEFAULT_LLM_API_KEY),
            app_config.USER_LLM_API_BASE_URL_KEY: api_base_url,
            app_config.USER_LLM_MODEL_NAME_KEY: current_profile.get("model_name", app_config.DEFAULT_LLM_MODEL_NAME),
            app_config.USER_LLM_TEMPERATURE_KEY: current_profile.get("temperature", app_config.DEFAULT_LLM_TEMPERATURE)
        }

        self.thread = QThread()
        self.worker = ConversionWorker(
            input_json_path=input_path,
            output_dir=output_dir,
            srt_processor=self.srt_processor,
            source_format="elevenlabs" if mode == "free_transcription" else source_format,
            input_mode=mode,
            free_transcription_params=free_params,
            elevenlabs_stt_client=self.elevenlabs_client,
            llm_config=llm_config
        )
        self.worker.moveToThread(self.thread)

        # 连接信号
        self.worker.signals.progress.connect(self.progress_updated)
        self.worker.signals.log_message.connect(self.log_message)
        self.worker.signals.finished.connect(self._on_worker_finished)

        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def _on_worker_finished(self, msg: str, success: bool):
        """
        处理 Worker 完成信号

        Args:
            msg: 完成消息
            success: 是否成功
        """
        # 清理线程
        if self.thread:
            self.thread.quit()
            self.thread.wait()

        if self._is_batch:
            if not success:
                self.log_message.emit(f"处理失败: {msg}")
            else:
                self.log_message.emit("处理成功。")

            self._current_batch_index += 1
            self._process_next_batch_item()
        else:
            self.task_finished.emit(msg, success)