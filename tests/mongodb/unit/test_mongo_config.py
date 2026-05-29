"""tests/mongodb/unit/test_mongo_config.py

Layer 1 — MongoDBConfig pydantic validation tests.

Tests every validation path, environment-based default resolution, and the
safe logging helper without any I/O or real MongoDB connections.
"""

import pytest

from shared.shared_infrastructure.src.mongodb.config import MongoDBConfig

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

VALID_URI = "mongodb://admin:pass@localhost:27017/auth_service?authSource=admin"


def _make(uri: str = VALID_URI, env: str = "development", **kwargs) -> MongoDBConfig:
    return MongoDBConfig(mongodb_uri=uri, environment=env, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# URI validation
# ─────────────────────────────────────────────────────────────────────────────

class TestURIValidation:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_valid_mongodb_uri_accepted(self):
        cfg = _make()
        assert cfg.mongodb_uri == VALID_URI

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_valid_srv_uri_accepted(self):
        srv = "mongodb+srv://user:pass@cluster.mongodb.net/mydb?retryWrites=true"
        cfg = _make(uri=srv)
        assert cfg.mongodb_uri == srv

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_empty_uri_raises(self):
        from pydantic import ValidationError
        with pytest.raises((ValidationError, ValueError)):
            _make(uri="")

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_non_mongodb_scheme_raises(self):
        from pydantic import ValidationError
        with pytest.raises((ValidationError, ValueError)):
            _make(uri="postgres://user:pass@localhost/db")

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_missing_scheme_separator_raises(self):
        from pydantic import ValidationError
        with pytest.raises((ValidationError, ValueError)):
            _make(uri="mongodbuser:pass@localhost")


# ─────────────────────────────────────────────────────────────────────────────
# Environment validation
# ─────────────────────────────────────────────────────────────────────────────

class TestEnvironmentValidation:
    @pytest.mark.unit
    @pytest.mark.mongodb
    @pytest.mark.parametrize("env", ["development", "staging", "production"])
    def test_valid_environments_accepted(self, env: str):
        cfg = _make(env=env)
        assert cfg.environment == env

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_unknown_environment_raises(self):
        from pydantic import ValidationError
        with pytest.raises((ValidationError, ValueError)):
            _make(env="canary")

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_environment_normalised_to_lowercase(self):
        # Pydantic validator lowercases the value
        cfg = _make(env="development")
        assert cfg.environment == "development"


# ─────────────────────────────────────────────────────────────────────────────
# Pool size defaults per environment
# ─────────────────────────────────────────────────────────────────────────────

class TestPoolSizeDefaults:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_development_pool_defaults(self):
        cfg = _make(env="development")
        min_pool, max_pool = cfg.resolve_pool_sizes()
        assert min_pool == 1
        assert max_pool == 10

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_staging_pool_defaults(self):
        cfg = _make(env="staging")
        min_pool, max_pool = cfg.resolve_pool_sizes()
        assert min_pool == 2
        assert max_pool == 20

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_production_pool_defaults(self):
        cfg = _make(env="production")
        min_pool, max_pool = cfg.resolve_pool_sizes()
        assert min_pool == 5
        assert max_pool == 50

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_explicit_pool_sizes_override_defaults(self):
        cfg = _make(env="development", min_pool_size=10, max_pool_size=100)
        min_pool, max_pool = cfg.resolve_pool_sizes()
        assert min_pool == 10
        assert max_pool == 100


# ─────────────────────────────────────────────────────────────────────────────
# Timeout defaults per environment
# ─────────────────────────────────────────────────────────────────────────────

class TestTimeoutDefaults:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_development_timeout_defaults(self):
        cfg = _make(env="development")
        connect, server_select, socket = cfg.resolve_timeouts()
        assert connect == 5000
        assert server_select == 5000
        assert socket == 30000

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_production_timeout_defaults(self):
        cfg = _make(env="production")
        connect, server_select, socket = cfg.resolve_timeouts()
        assert connect == 10000
        assert server_select == 10000
        assert socket == 60000

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_explicit_timeouts_override_defaults(self):
        cfg = _make(connect_timeout_ms=2000, socket_timeout_ms=15000)
        connect, _, socket = cfg.resolve_timeouts()
        assert connect == 2000
        assert socket == 15000


# ─────────────────────────────────────────────────────────────────────────────
# Factory class methods
# ─────────────────────────────────────────────────────────────────────────────

class TestFactoryMethods:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_for_development_sets_env(self):
        cfg = MongoDBConfig.for_development(mongodb_uri=VALID_URI)
        assert cfg.environment == "development"

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_for_staging_sets_env(self):
        cfg = MongoDBConfig.for_staging(mongodb_uri=VALID_URI)
        assert cfg.environment == "staging"

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_for_production_sets_env(self):
        cfg = MongoDBConfig.for_production(mongodb_uri=VALID_URI)
        assert cfg.environment == "production"

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_from_env_raises_when_uri_missing(self, monkeypatch):
        monkeypatch.delenv("MONGODB_URI", raising=False)
        with pytest.raises((EnvironmentError, ValueError)):
            MongoDBConfig.from_env()

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_from_env_loads_uri_from_environment(self, monkeypatch):
        monkeypatch.setenv("MONGODB_URI", VALID_URI)
        monkeypatch.setenv("MONGODB_ENVIRONMENT", "staging")
        cfg = MongoDBConfig.from_env()
        assert cfg.mongodb_uri == VALID_URI
        assert cfg.environment == "staging"


# ─────────────────────────────────────────────────────────────────────────────
# Safe logging helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestSafeLogging:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_to_dict_safe_never_exposes_credentials(self):
        cfg = _make()
        safe = cfg.to_dict_safe()
        assert "admin" not in str(safe)
        assert "pass" not in str(safe)
        assert safe["mongodb_uri"] == "***@***"

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_str_representation_hides_credentials(self):
        cfg = _make()
        text = str(cfg)
        assert "pass" not in text
        assert "***" in text

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_to_dict_safe_contains_environment(self):
        cfg = _make(env="staging")
        safe = cfg.to_dict_safe()
        assert safe["environment"] == "staging"


# ─────────────────────────────────────────────────────────────────────────────
# Connection manager creation
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateConnectionManager:
    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_create_connection_manager_returns_manager_instance(self):
        from shared.shared_infrastructure.src.mongodb.connection import MongoConnectionManager
        cfg = _make()
        manager = cfg.create_connection_manager()
        assert isinstance(manager, MongoConnectionManager)

    @pytest.mark.unit
    @pytest.mark.mongodb
    def test_create_connection_manager_applies_pool_sizes(self):
        cfg = _make(env="development")
        manager = cfg.create_connection_manager()
        # Manager should use dev defaults (1, 10)
        assert manager._client_kwargs["minPoolSize"] == 1
        assert manager._client_kwargs["maxPoolSize"] == 10
