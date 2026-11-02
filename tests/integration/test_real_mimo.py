"""真实 MiMo API 测试。

需要设置 MIMO_API_KEY，单独运行：pytest -m real_api
默认离线测试不会执行这些用例。
"""

import os

import pytest
from langchain_core.messages import HumanMessage

from app.core.config import Settings
from app.core.llm import create_llm

pytestmark = pytest.mark.real_api

requires_key = pytest.mark.skipif(
    not os.getenv("MIMO_API_KEY"),
    reason="需要设置 MIMO_API_KEY 环境变量",
)


@requires_key
def test_real_mimo_chat() -> None:
    """真实 MiMo 普通对话调用。"""
    llm = create_llm()
    response = llm.invoke([HumanMessage(content="请只回复四个字：连接正常")])
    assert isinstance(response.content, str)
    assert response.content.strip()


@requires_key
def test_real_mimo_model_switch() -> None:
    """Pro 和 Flash 可通过配置切换。"""
    for model in ("mimo-v2.6-pro", "mimo-v2.6-flash"):
        settings = Settings(_env_file=None, mimo_model=model)
        llm = create_llm(settings)
        response = llm.invoke([HumanMessage(content="请只回复四个字：模型可用")])
        assert isinstance(response.content, str)
        assert response.content.strip()
