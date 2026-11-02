"""领域异常与错误分类单元测试。"""

from app.core.exceptions import (
    AgentWorkflowError,
    InputValidationError,
    LLMAuthError,
    LLMConfigError,
    LLMServiceError,
    LLMTimeoutError,
    ModelResponseError,
    NetOpsError,
    TargetDeniedError,
    classify_llm_error,
    sanitize,
)


def test_sanitize_masks_api_key() -> None:
    """日志脱敏：疑似 API Key 被遮蔽。"""
    masked = sanitize("error sk-abcdefgh12345678 happened")
    assert "sk-abcdefgh12345678" not in masked
    assert "sk-***" in masked


def test_sanitize_keeps_normal_text() -> None:
    """普通文本不被改动。"""
    assert sanitize("timeout on ping") == "timeout on ping"


def test_classify_timeout() -> None:
    """超时异常映射为 LLMTimeoutError。"""
    err = classify_llm_error(TimeoutError("Request timed out"))
    assert isinstance(err, LLMTimeoutError)
    assert err.error_code == "llm_timeout"


def test_classify_auth_error() -> None:
    """认证失败映射为 LLMAuthError（不可重试）。"""
    err = classify_llm_error(Exception("Incorrect API key provided"))
    assert isinstance(err, LLMAuthError)
    assert err.error_code == "llm_auth_error"


def test_classify_rate_limit() -> None:
    """限流映射为 LLMServiceError（可重试）。"""
    err = classify_llm_error(Exception("Rate limit exceeded"))
    assert isinstance(err, LLMServiceError)


def test_classify_connection_error() -> None:
    """连接错误映射为 LLMServiceError。"""
    err = classify_llm_error(Exception("Connection refused 503"))
    assert isinstance(err, LLMServiceError)


def test_classify_generic_error() -> None:
    """未知异常映射为 AgentWorkflowError。"""
    err = classify_llm_error(ValueError("something odd"))
    assert isinstance(err, AgentWorkflowError)


def test_safe_message_not_leaking_detail() -> None:
    """对外 safe_message 不含内部细节。

    注：`sk-secret123456` 是脱敏测试用假 key，非真实凭证，
    仅用于验证 sanitize 逻辑不泄漏真实密钥。
    """
    err = LLMConfigError("MIMO_API_KEY=sk-secret123456")
    assert "sk-secret123456" not in err.safe_message
    assert "sk-secret123456" in err.detail


def test_error_codes_unique() -> None:
    """各错误码唯一。"""
    codes = {
        NetOpsError.error_code,
        LLMConfigError.error_code,
        LLMAuthError.error_code,
        LLMTimeoutError.error_code,
        LLMServiceError.error_code,
        ModelResponseError.error_code,
        AgentWorkflowError.error_code,
        InputValidationError.error_code,
        TargetDeniedError.error_code,
    }
    assert len(codes) == 9
