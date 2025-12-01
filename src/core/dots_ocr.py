import os
import re
import logging
from typing import Optional

# 尝试导入 gradio_client
try:
    from gradio_client import Client, handle_file
    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False

# 配置日志
logger = logging.getLogger(__name__)

def clean_ocr_text(raw_text: str) -> str:
    """
    对 OCR 结果进行增强版清洗 (针对 Markdown Render Preview 格式优化)：
    1. 去除行首的数字编号 (如 "1 文字", "20 文字")
    2. 去除页码标识 (如 "1/6", "2 / 5")
    3. 规范化过长的省略号 (如 "･･････" -> "……")
    4. 过滤系统日志
    """
    if not raw_text:
        return ""

    lines = raw_text.split('\n')
    cleaned_lines = []

    # [正则定义]

    # 1. 行首编号匹配：匹配 "1 文字", "20 文字"
    # Markdown Preview 的格式通常是 "数字+空格+内容"
    line_prefix_pattern = re.compile(r'^\d+\s+(?=\S)')

    # 2. 页码匹配：匹配 "1/6", "2 / 5" 等独立行
    page_number_pattern = re.compile(r'^\s*\d+\s*/\s*\d+\s*$')

    # 3. 匹配各种类型的连续点号/分隔符 (包含半角中点･ 全角中点・ 句号。)
    # 只要连续出现2次以上，就视为省略号或分隔线
    ellipsis_pattern = re.compile(r'[\.。・･]{2,}')

    for line in lines:
        line = line.strip()

        # --- 过滤阶段 (丢弃整行) ---

        # 1. 过滤空行
        if not line:
            continue

        # 2. 过滤 Python/Gradio 警告日志
        if "site-packages" in line or "UserWarning" in line or "gradio_client" in line:
            continue

        # 3. 过滤页码行 (如 "1/6")
        if page_number_pattern.match(line):
            continue

        # 4. 过滤纯数字行 (防止漏网的孤立行号)
        # 注意：如果行首编号正则没删干净，这里会作为兜底
        if line.isdigit():
            continue

        # --- 清洗阶段 (修改行内容) ---

        # 5. 去除行首的编号
        # 例: "20 「あああ…" -> "「あああ…"
        line = line_prefix_pattern.sub('', line)

        # 6. 规范化过长的省略号/分隔符
        # 例: "･･････" -> "……"
        line = ellipsis_pattern.sub('……', line)

        # 7. 简单去噪：去除仅包含单个无意义字符的行
        # 保留 "■" (标题) 和常见文字，过滤 "a", "f" 等 OCR 碎片
        # 正则含义：匹配 字母、数字、汉字、假名、■。如果超出这个范围且长度为1，则丢弃
        if len(line) == 1 and not re.match(r'[a-zA-Z0-9一-龯ぁ-ん■]', line):
            continue

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)

def run_dots_ocr(file_path: str) -> Optional[str]:
    """
    调用 Dots OCR 进行识别 (PDF 或图片)
    """
    if not GRADIO_AVAILABLE:
        logger.error("请先安装 gradio_client: pip install gradio_client")
        return "错误: 未安装 gradio_client 库，无法使用 OCR 功能。"

    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return None

    try:
        logger.info(f"开始 Dots OCR 识别: {file_path}")

        # 初始化客户端
        client = Client("https://dotsocr.xiaohongshu.com/")

        # 调用推理接口 - 使用 prompt_layout_all_en 获得更好的英文识别效果
        result = client.predict(
            test_image_input="",
            file_input=handle_file(file_path),
            prompt_mode="prompt_layout_all_en",
            server_ip="127.0.0.1",
            server_port=8000,
            min_pixels=3136,
            max_pixels=11289600,
            fitz_preprocess=True,
            api_name="/process_image_inference"
        )

        # 结果索引说明:
        # 0: Layout Preview (Image)
        # 1: Info Box (Markdown)
        # 2: Markdown Render Preview (Markdown) <- 质量最好，人工清洗过
        # 3: Markdown Raw Text (Textbox) <- 原始识别，噪音多

        # 优先获取 Index 2 (Markdown Render Preview)
        if isinstance(result, (list, tuple)) and len(result) > 2:
            raw_text = result[2]

            # 只有当 Index 2 为空时，才回退到 Index 3
            if not raw_text and len(result) > 3:
                logger.warning("Preview 为空，回退到 Raw Text")
                raw_text = result[3]

            if not raw_text:
                return "OCR 识别结果为空。"

            # 执行清洗
            final_text = clean_ocr_text(raw_text)
            logger.info(f"OCR 识别完成，清洗后长度: {len(final_text)}")
            return final_text
        else:
            logger.error(f"OCR 返回数据格式异常: {result}")
            return None

    except Exception as e:
        error_msg = f"Dots OCR 识别失败: {str(e)}"
        logger.error(error_msg)
        return None