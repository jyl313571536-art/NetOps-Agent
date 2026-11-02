"""日志配置单元测试。"""

import logging

from app.core.logging import setup_logging


def test_setup_logging_adds_handler() -> None:
    """初始化后根 logger 有 StreamHandler。"""
    setup_logging("INFO")
    assert logging.getLogger().handlers


def test_setup_logging_idempotent() -> None:
    """重复初始化不叠加 handler。"""
    setup_logging("INFO")
    count_before = len(logging.getLogger().handlers)
    setup_logging("DEBUG")
    assert len(logging.getLogger().handlers) == count_before


def test_setup_logging_level() -> None:
    """日志级别可设置。"""
    setup_logging("warning")
    assert logging.getLogger().level == logging.WARNING
