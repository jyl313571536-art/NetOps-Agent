"""应用配置管理模块。

通过 pydantic-settings 从环境变量或 .env 文件加载配置。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置项。

    环境变量名与字段名对应，例如 mimo_api_key 对应 MIMO_API_KEY。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Xiaomi MiMo 模型配置
    mimo_api_key: str = ""
    mimo_base_url: str = "https://token-plan-cn.xiaomimimo.com/v1"
    mimo_model: str = "mimo-v2.6-pro"
    mimo_fast_model: str = "mimo-v2.6-flash"
    mimo_timeout: int = 60

    # Agent 执行限制（Phase 2 起生效）
    agent_max_steps: int = 3
    agent_timeout: float = 120.0

    # 网络诊断安全限制
    # 注意：当前默认放开目标白名单（diag_allow_all_targets=True），
    # 仅做输入格式校验，不做目标范围限制。详见 README 安全警示。
    diag_allow_all_targets: bool = False
    diag_allowed_targets: str = "localhost,127.0.0.1,::1"
    diag_timeout: float = 10.0

    # RAG 知识库配置（Phase 3 起生效）
    rag_kb_dir: str = "data/knowledge_base"
    rag_persist_dir: str = "data/chroma_db"
    rag_embedding_model: str = "BAAI/bge-small-zh-v1.5"
    rag_top_k: int = 4
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 50

    # 诊断记录存储（Phase 4 起生效）
    storage_db_path: str = "data/netops.db"

    # 应用配置
    app_name: str = "NetOps Agent"
    app_version: str = "0.1.0"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例。"""
    return Settings()
