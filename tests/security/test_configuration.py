import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_invalid_settings_do_not_print_password_fragments():
    with pytest.raises(ValidationError) as caught:
        Settings(
            _env_file=None,
            app_env="production",
            demo_mode=True,
            postgres_password="FAKE_AUDIT_SECRET_NOT_REAL",
        )
    rendered = str(caught.value)
    assert "DEMO_MODE must be disabled" in rendered
    assert "NOT_REAL" not in rendered
    assert "input_value" not in rendered


@pytest.mark.parametrize("port", [0, -1, 65536])
def test_invalid_database_ports_fail_at_configuration_boundary(port):
    with pytest.raises(ValidationError, match="postgres_port"):
        Settings(_env_file=None, postgres_port=port)


def test_whitespace_is_not_a_production_database_password():
    with pytest.raises(ValidationError, match="POSTGRES_PASSWORD is required"):
        Settings(_env_file=None, app_env="production", demo_mode=False, postgres_password="   ")


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError, match="Production CORS origins must be explicit"):
        Settings(
            _env_file=None,
            app_env="production",
            demo_mode=False,
            postgres_password="fake-test-only",
            cors_origins=["*"],
        )
