"""Agent 领域异常定义。

对外只暴露 safe_message，detail 仅写入日志，避免泄露凭证。
每个异常类自带 http_status，Web 层直接读取，不再手工维护映射表。
"""

import re

_SAFE_KEY_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")


def sanitize(text: str) -> str:
    """移除疑似 API Key 的内容后再写日志。"""
    return _SAFE_KEY_RE.sub("sk-***", text)


class NetOpsError(Exception):
    """NetOps Agent 基础异常。"""

    error_code = "internal_error"
    safe_message = "服务器内部错误"
    http_status = 500

    def __init__(self, detail: str = "") -> None:
        """detail 仅用于日志记录，不直接返回给客户端。"""
        self.detail = detail
        super().__init__(detail or self.safe_message)


class LLMConfigError(NetOpsError):
    """模型配置错误，例如 API Key 缺失。不可重试。"""

    error_code = "llm_config_error"
    safe_message = "模型服务未配置，请检查 API Key 配置"
    http_status = 503


class LLMAuthError(NetOpsError):
    """API Key 无效或认证失败。不可重试。"""

    error_code = "llm_auth_error"
    safe_message = "模型服务认证失败，请检查 API Key 配置"
    http_status = 503


class LLMTimeoutError(NetOpsError):
    """模型请求超时。可重试。"""

    error_code = "llm_timeout"
    safe_message = "模型服务请求超时，请稍后重试"
    http_status = 504


class LLMServiceError(NetOpsError):
    """模型服务不可用、限流等临时错误。可重试。"""

    error_code = "llm_service_error"
    safe_message = "模型服务暂时不可用，请稍后重试"
    http_status = 503


class ModelResponseError(NetOpsError):
    """模型响应异常。"""

    error_code = "model_response_error"
    safe_message = "模型响应异常，请稍后重试"
    http_status = 502


class AgentWorkflowError(NetOpsError):
    """Agent 工作流执行异常。"""

    error_code = "agent_workflow_error"
    safe_message = "Agent 工作流执行异常"
    http_status = 500


class InputValidationError(NetOpsError):
    """工具入参格式或范围校验失败。不可重试。"""

    error_code = "invalid_input"
    safe_message = "参数校验失败"
    http_status = 400


class TargetDeniedError(NetOpsError):
    """目标主机不在诊断白名单内。不可重试。"""

    error_code = "target_denied"
    safe_message = "目标主机不在允许诊断范围内"
    http_status = 403


def classify_llm_error(exc: Exception) -> NetOpsError:
    """将底层模型异常映射为领域异常。

    优先按 SDK 异常类型显式映射；类型未知时退回名称/消息特征分类。
    可恢复错误（超时、限流、服务不可用）由 ChatOpenAI 的 max_retries
    按指数退避重试；无效 Key、参数错误等不可恢复错误不重试。
    """
    typed = _classify_by_type(exc)
    if typed is not None:
        return typed

    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "timeout" in name or "timed out" in text:
        return LLMTimeoutError(str(exc))
    if "authentication" in name or "401" in text or "api key" in text:
        return LLMAuthError(str(exc))
    if "ratelimit" in name or "429" in text or ("rate" in text and "limit" in text):
        return LLMServiceError(str(exc))
    if "connection" in name or "502" in text or "503" in text or "unavailable" in text:
        return LLMServiceError(str(exc))
    return AgentWorkflowError(str(exc))


def _classify_by_type(exc: Exception) -> NetOpsError | None:
    """按 openai SDK 的异常类型显式映射，未知类型返回 None。"""
    try:
        import openai
    except ImportError:
        return None

    if isinstance(exc, openai.APITimeoutError):
        return LLMTimeoutError(str(exc))
    if isinstance(exc, openai.AuthenticationError):
        return LLMAuthError(str(exc))
    if isinstance(exc, openai.RateLimitError):
        return LLMServiceError(str(exc))
    if isinstance(exc, openai.APIConnectionError):
        return LLMServiceError(str(exc))
    if isinstance(exc, openai.InternalServerError):
        return LLMServiceError(str(exc))
    return None
