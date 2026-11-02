"""模型创建模块单元测试。"""

import pytest
from langchain_openai import ChatOpenAI

from app.core.config import Settings
from app.core.exceptions import LLMConfigError
from app.core.llm import create_llm


def test_create_llm_requires_api_key() -> None:
    """API Key 缺失时抛出 LLMConfigError。"""
    settings = Settings(_env_file=None, mimo_api_key="")
    with pytest.raises(LLMConfigError):
        create_llm(settings)


def test_create_llm_returns_chat_model() -> None:
    """配置完整时返回 ChatOpenAI 实例。"""
    settings = Settings(
        _env_file=None,
        mimo_api_key="test-key",
        mimo_model="mimo-v2.6-pro",
    )
    llm = create_llm(settings)
    assert isinstance(llm, ChatOpenAI)


def test_create_llm_model_switch() -> None:
    """Pro 和 Flash 可通过配置切换。"""
    for model in ("mimo-v2.6-pro", "mimo-v2.6-flash"):
        settings = Settings(_env_file=None, mimo_api_key="test-key", mimo_model=model)
        llm = create_llm(settings)
        assert llm.model_name == model
