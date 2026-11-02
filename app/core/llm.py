"""Xiaomi MiMo 模型创建模块。

只负责读取配置并创建 ChatOpenAI 实例，Agent 节点不得直接创建模型对象。
"""

from langchain_openai import ChatOpenAI

from app.core.config import Settings, get_settings
from app.core.exceptions import LLMConfigError


def create_llm(
    settings: Settings | None = None, model: str | None = None
) -> ChatOpenAI:
    """创建 Xiaomi MiMo 聊天模型实例。

    Args:
        settings: 应用配置，默认读取全局配置。
        model: 模型型号覆盖；不传时使用配置中的 mimo_model。

    Returns:
        已配置模型、地址、超时和重试策略的 ChatOpenAI 实例。

    Raises:
        LLMConfigError: API Key 未配置时抛出。
    """
    cfg = settings or get_settings()
    if not cfg.mimo_api_key.strip():
        raise LLMConfigError("MIMO_API_KEY 未配置")
    return ChatOpenAI(
        model=model or cfg.mimo_model,
        api_key=cfg.mimo_api_key,
        base_url=cfg.mimo_base_url,
        timeout=cfg.mimo_timeout,
        # 可恢复错误（超时、限流、5xx）按指数退避最多重试 2 次；
        # 无效 Key、参数错误等不可恢复错误不重试。
        max_retries=2,
    )
