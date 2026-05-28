"""
模型输出 token 上限查表工具

根据模型名称查询最大输出 token 数。
供 LLM 分段、摘要等模块共用，避免因硬编码 max_tokens 导致输出截断。

关键：很多模型默认输出 token 很低（DeepSeek 4096, Kimi 1024, Grok 600），
必须显式设置 max_tokens 为模型支持的最大值，否则输出会被截断。

作者: fuxiaomoke
"""


# ---------------------------------------------------------------------------
# 模型最大输出 token 查表
# ---------------------------------------------------------------------------
# 数据更新于 2026-05-28，来源: 各厂商官方文档/API

MODEL_OUTPUT_RULES = [
    # (关键词, max_output_tokens)
    # DeepSeek
    ("deepseek-v4", 384_000),   # V4 Pro/Flash: 1M context / 384K output
    ("deepseek-r2", 64_000),    # R2推理: 128K context / 64K output
    ("deepseek-r1", 64_000),    # R1推理: 128K context / 64K output
    ("deepseek-v3", 16_000),    # V3: 128K context / 16K output
    ("deepseek", 16_000),       # fallback
    # OpenAI
    ("gpt-5.5", 128_000),       # 1M context / 128K output
    ("gpt-5.4-mini", 128_000),  # 400K context / 128K output
    ("gpt-5.4", 128_000),       # 1.05M context / 128K output
    ("gpt-5.2", 32_000),        # 256K context / 32K output
    ("gpt-5", 128_000),         # 400K context / 128K output
    ("gpt-4o-mini", 16_000),
    ("gpt-4o", 16_000),         # 128K context / 16K output
    ("gpt", 16_000),
    # Google Gemini
    ("gemini-3.1-pro", 64_000),  # 2M context / 64K output
    ("gemini-3.1-flash", 64_000),
    ("gemini-3", 64_000),        # 1M input / 64K output
    ("gemini-2.5", 65_000),
    ("gemini-1.5", 65_000),
    ("gemini", 64_000),
    # Anthropic Claude
    ("claude-opus-4-7", 128_000),
    ("claude-opus-4-6", 128_000),
    ("claude-opus-4-5", 64_000),
    ("claude-sonnet-4-6", 128_000),
    ("claude-sonnet-4", 16_000),
    ("claude-opus-4", 32_000),
    ("claude-haiku", 8_000),
    ("claude", 64_000),
    # 阿里 Qwen
    ("qwen3.6-max", 64_000),
    ("qwen3.5-plus", 64_000),
    ("qwen3-max", 64_000),
    ("qwen-plus", 64_000),
    ("qwen-long", 16_000),
    ("qwen", 32_000),
    # 智谱 GLM
    ("glm-5", 16_000),
    ("glm-4", 16_000),
    ("glm", 16_000),
    # Moonshot Kimi
    ("kimi-k2", 49_152),
    ("moonshot-v1-128k", 32_000),
    ("moonshot-v1-32k", 8_000),
    ("moonshot-v1-8k", 4_000),
    ("moonshot", 32_000),
    ("kimi", 32_000),
    # MiniMax
    ("minimax-m2", 16_000),
    ("minimax-m1", 80_000),
    ("abab6.5", 245_760),
    ("minimax", 65_536),
    # xAI Grok
    ("grok-4.3", 32_000),
    ("grok-4.1-fast", 32_000),
    ("grok-4.1", 32_000),
    ("grok", 32_000),
]

DEFAULT_MAX_OUTPUT_TOKENS = 8192


def get_max_output_tokens(model_name: str) -> int:
    """根据模型名称获取 LLM 调用时的 max_output_tokens"""
    model_lower = model_name.lower() if model_name else ""
    for keyword, max_tokens in MODEL_OUTPUT_RULES:
        if keyword in model_lower:
            return max_tokens
    return DEFAULT_MAX_OUTPUT_TOKENS
