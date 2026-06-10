from pathlib import Path

import pytest

from authsome.server.config import ServerConfig


def test_server_config_reads_redis_url(monkeypatch) -> None:
    monkeypatch.setenv("AUTHSOME_REDIS_URL", "redis://localhost:6379/0")

    config = ServerConfig()

    assert config.redis_url == "redis://localhost:6379/0"


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


def test_server_config_rejects_invalid_postgres_pool_range() -> None:
    with pytest.raises(ValueError, match="postgres_pool_min_size must be less than or equal to postgres_pool_max_size"):
        ServerConfig(postgres_pool_min_size=10, postgres_pool_max_size=2)
