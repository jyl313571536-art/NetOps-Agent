"""配置管理单元测试。"""

from app.core.config import Settings


def test_settings_defaults() -> None:
    """默认值与 CLAUDE.md 约定一致。"""
    settings = Settings(_env_file=None, mimo_api_key="")
    assert settings.mimo_base_url == "https://token-plan-cn.xiaomimimo.com/v1"
    assert settings.mimo_model == "mimo-v2.6-pro"
    assert settings.mimo_timeout == 60
    assert settings.app_name == "NetOps Agent"


def test_settings_from_env(monkeypatch) -> None:
    """环境变量可覆盖默认配置。"""
    monkeypatch.setenv("MIMO_MODEL", "mimo-v2.6-flash")
    monkeypatch.setenv("MIMO_TIMEOUT", "30")
    settings = Settings(_env_file=None, mimo_api_key="test-key")
    assert settings.mimo_model == "mimo-v2.6-flash"
    assert settings.mimo_timeout == 30
