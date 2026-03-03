import pytest

from nyxora.utils.config import Config
from nyxora.utils.exceptions import ConfigError


def test_config_default_initialization():
    config = Config()
    assert config.get("vault.timeout") == 300
    assert config.get("intel.hibp_enabled") is True

def test_config_load_and_save(tmp_path):
    config_file = tmp_path / "config.yaml"
    config = Config(config_path=config_file)
    config.set("ui.color", False)
    config.save()

    assert config_file.exists()

    # Load into a new instance
    new_config = Config(config_path=config_file)
    new_config.load()
    assert new_config.get("ui.color") is False

def test_config_environment_override(monkeypatch):
    monkeypatch.setenv("NYX_TIMEOUT", "600")
    monkeypatch.setenv("NYX_DEBUG", "True")
    config = Config()
    config.load()

    assert config.get("ui.debug") is True
    assert config.get("vault.timeout") == 600

def test_config_update():
    config = Config()
    config.set("ui.color", False)
    assert config.get("ui.color") is False

def test_config_invalid_key():
    config = Config()
    # set() does not raise by default as it creates dict hierarchies
    config.set("invalid.key", "value")
    # get() just returns None
    assert config.get("doesnotexist") is None

def test_config_validation():
    config = Config()
    # Test valid
    config.set("vault.timeout", 100)
    config.validate()  # Should not raise

    # Test invalid
    config.set("vault.timeout", "not_an_int")
    with pytest.raises(ConfigError):
        config.validate()
