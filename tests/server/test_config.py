from pathlib import Path

import pytest

from authsome.server.config import ServerConfig


def test_server_config_reads_redis_url(monkeypatch) -> None:
    monkeypatch.setenv("AUTHSOME_REDIS_URL", "redis://localhost:6379/0")

    config = ServerConfig()

    assert config.redis_url == "redis://localhost:6379/0"


def test_server_config_defaults_to_dev_env(monkeypatch) -> None:
    monkeypatch.delenv("AUTHSOME_ENV", raising=False)

    config = ServerConfig()

    assert config.env == "dev"


def test_server_config_reads_authsome_database_url(monkeypatch) -> None:
    monkeypatch.setenv("AUTHSOME_DATABASE_URL", "postgresql://authsome:secret@localhost/authsome")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    config = ServerConfig()

    assert config.database_url == "postgresql://authsome:secret@localhost/authsome"
    assert config.database == "postgresql://authsome:secret@localhost/authsome"


def test_server_config_keeps_legacy_database_url_alias(monkeypatch) -> None:
    monkeypatch.delenv("AUTHSOME_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://legacy:secret@localhost/authsome")

    config = ServerConfig()

    assert config.database_url == "postgresql://legacy:secret@localhost/authsome"


def test_server_config_exposes_postgres_pool_settings(monkeypatch) -> None:
    monkeypatch.setenv("AUTHSOME_POSTGRES_POOL_MIN_SIZE", "2")
    monkeypatch.setenv("AUTHSOME_POSTGRES_POOL_MAX_SIZE", "9")
    expected_min_pool_size = 2
    expected_max_pool_size = 9

    config = ServerConfig()

    assert config.postgres_pool_min_size == expected_min_pool_size
    assert config.postgres_pool_max_size == expected_max_pool_size


def test_server_config_defaults_preserve_local_paths(tmp_path: Path) -> None:
    config = ServerConfig(home=tmp_path)

    assert config.redis_url is None
    assert config.database == str(tmp_path / "server" / "authsome.db")
    assert config.kv_store_dir == tmp_path / "server" / "kv_store"


def test_server_config_requires_database_url_in_prod(monkeypatch) -> None:
    monkeypatch.setenv("AUTHSOME_ENV", "prod")
    monkeypatch.delenv("AUTHSOME_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AUTHSOME_REDIS_URL", "redis://localhost:6379/0")

    with pytest.raises(ValueError, match="AUTHSOME_DATABASE_URL is required when AUTHSOME_ENV=prod"):
        ServerConfig()


def test_server_config_requires_redis_url_in_prod(monkeypatch) -> None:
    monkeypatch.setenv("AUTHSOME_ENV", "prod")
    monkeypatch.setenv("AUTHSOME_DATABASE_URL", "postgresql://authsome:secret@localhost/authsome")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("AUTHSOME_REDIS_URL", raising=False)

    with pytest.raises(ValueError, match="AUTHSOME_REDIS_URL is required when AUTHSOME_ENV=prod"):
        ServerConfig()


def test_server_config_requires_postgres_database_url_in_prod(monkeypatch) -> None:
    monkeypatch.setenv("AUTHSOME_ENV", "prod")
    monkeypatch.setenv("AUTHSOME_DATABASE_URL", "sqlite:////tmp/authsome.db")
    monkeypatch.setenv("AUTHSOME_REDIS_URL", "redis://localhost:6379/0")

    with pytest.raises(ValueError, match="AUTHSOME_DATABASE_URL must be a Postgres URL when AUTHSOME_ENV=prod"):
        ServerConfig()


def test_server_config_accepts_prod_with_database_and_redis_urls(monkeypatch) -> None:
    monkeypatch.setenv("AUTHSOME_ENV", "prod")
    monkeypatch.setenv("AUTHSOME_DATABASE_URL", "postgresql://authsome:secret@localhost/authsome")
    monkeypatch.setenv("AUTHSOME_REDIS_URL", "redis://localhost:6379/0")

    config = ServerConfig()

    assert config.env == "prod"
    assert config.database_url == "postgresql://authsome:secret@localhost/authsome"
    assert config.redis_url == "redis://localhost:6379/0"


def test_server_config_rejects_invalid_postgres_pool_range() -> None:
    with pytest.raises(ValueError, match="postgres_pool_min_size must be less than or equal to postgres_pool_max_size"):
        ServerConfig(postgres_pool_min_size=10, postgres_pool_max_size=2)
