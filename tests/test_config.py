# tests/test_config.py
from __future__ import annotations
import os
import pytest
from pathlib import Path

from devman.config import UserConfig, ConfigManager
from devman.exceptions import ConfigurationError


class TestUserConfig:
    """Test UserConfig functionality."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = UserConfig()
        
        assert config.default_python_version == "3.11"
        assert config.default_template == "python-lib"
        assert config.author_name == "Your Name"
        assert config.author_email == "you@example.com"
        assert config.use_nix is True
        assert config.use_docker is True
        assert config.use_just is True
        assert config.cache_enabled is True
        assert config.quiet_mode is False
        assert config.template_sources == {}
    
    def test_config_paths_order(self):
        """Test configuration file search order."""
        paths = UserConfig.get_config_paths()
        
        # Should always have at least the home directory fallback
        assert len(paths) >= 2
        
        # Last path should be home directory fallback
        assert paths[-1].name == ".devman.yml"
        assert paths[-1].parent == Path.home()
    
    def test_config_paths_with_env_override(self, tmp_path, monkeypatch):
        """Test configuration path with environment variable override."""
        config_file = tmp_path / "custom-config.yml"
        monkeypatch.setenv("DEVMAN_CONFIG", str(config_file))
        
        paths = UserConfig.get_config_paths()
        
        # First path should be the environment override
        assert paths[0] == config_file
    
    def test_config_paths_with_xdg(self, tmp_path, monkeypatch):
        """Test configuration path with XDG_CONFIG_HOME."""
        xdg_config = tmp_path / "config"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
        
        paths = UserConfig.get_config_paths()
        
        # Should include XDG path
        xdg_path = xdg_config / "devman" / "config.yml"
        assert xdg_path in paths
    
    def test_load_nonexistent_config(self):
        """Test loading config when no config file exists."""
        # This should return default config without errors
        config = UserConfig.load()
        
        assert config.default_python_version == "3.11"
        assert config.default_template == "python-lib"
    
    def test_load_valid_config(self, tmp_path, monkeypatch):
        """Test loading a valid configuration file."""
        config_file = tmp_path / ".devman.yml"
        config_content = """
default_python_version: "3.12"
default_template: "fastapi-api"
author_name: "Test User"
author_email: "test@example.com"
use_nix: false
cache_enabled: false
"""
        config_file.write_text(config_content)
        
        # Mock the config path to use our test file
        monkeypatch.setenv("DEVMAN_CONFIG", str(config_file))
        
        config = UserConfig.load()
        
        assert config.default_python_version == "3.12"
        assert config.default_template == "fastapi-api"
        assert config.author_name == "Test User"
        assert config.author_email == "test@example.com"
        assert config.use_nix is False
        assert config.cache_enabled is False
    
    def test_load_invalid_yaml(self, tmp_path, monkeypatch):
        """Test loading config with invalid YAML."""
        config_file = tmp_path / ".devman.yml"
        config_file.write_text("invalid: yaml: content: [")
        
        monkeypatch.setenv("DEVMAN_CONFIG", str(config_file))
        
        with pytest.raises(ConfigurationError, match="Invalid YAML"):
            UserConfig.load()
    
    def test_load_empty_config(self, tmp_path, monkeypatch):
        """Test loading empty configuration file."""
        config_file = tmp_path / ".devman.yml"
        config_file.write_text("")
        
        monkeypatch.setenv("DEVMAN_CONFIG", str(config_file))
        
        # Should return default config for empty file
        config = UserConfig.load()
        assert config.default_python_version == "3.11"
    
    def test_save_config(self, tmp_path):
        """Test saving configuration to file."""
        config = UserConfig(
            default_python_version="3.12",
            author_name="Test User",
            use_docker=False
        )
        
        config_file = tmp_path / "test-config.yml"
        saved_path = config.save(config_file)
        
        assert saved_path == config_file
        assert config_file.exists()
        
        # Verify content
        content = config_file.read_text()
        assert "default_python_version: '3.12'" in content
        assert "author_name: Test User" in content
        assert "use_docker: false" in content
    
    def test_save_config_creates_directory(self, tmp_path):
        """Test that save creates parent directories."""
        config = UserConfig()
        config_file = tmp_path / "deep" / "nested" / "config.yml"
        
        config.save(config_file)
        
        assert config_file.exists()
        assert config_file.parent.exists()
    
    def test_get_effective_config_path(self, tmp_path, monkeypatch):
        """Test getting the effective config path."""
        # No config exists
        config = UserConfig()
        assert config.get_effective_config_path() is None
        
        # Create a config file
        config_file = tmp_path / ".devman.yml"
        config_file.write_text("default_template: python-cli")
        monkeypatch.setenv("DEVMAN_CONFIG", str(config_file))
        
        config = UserConfig.load()
        assert config.get_effective_config_path() == config_file
    
    def test_update_setting_valid(self):
        """Test updating a valid configuration setting."""
        config = UserConfig()
        
        config.update_setting("default_python_version", "3.12")
        assert config.default_python_version == "3.12"
        
        config.update_setting("use_nix", "false")
        assert config.use_nix is False
        
        config.update_setting("author_name", "New Name")
        assert config.author_name == "New Name"
    
    def test_update_setting_boolean_values(self):
        """Test updating boolean settings with various formats."""
        config = UserConfig()
        
        # Test true values
        for true_val in ["true", "yes", "1", "on", "True", "YES"]:
            config.update_setting("use_nix", true_val)
            assert config.use_nix is True
        
        # Test false values
        for false_val in ["false", "no", "0", "off", "False", "NO"]:
            config.update_setting("use_nix", false_val)
            assert config.use_nix is False
    
    def test_update_setting_invalid_key(self):
        """Test updating a non-existent setting."""
        config = UserConfig()
        
        with pytest.raises(ConfigurationError, match="Unknown config key"):
            config.update_setting("nonexistent_key", "value")
    
    def test_update_setting_invalid_boolean(self):
        """Test updating boolean setting with invalid value."""
        config = UserConfig()
        
        with pytest.raises(ConfigurationError, match="Invalid boolean value"):
            config.update_setting("use_nix", "maybe")


class TestConfigManager:
    """Test ConfigManager functionality."""
    
    def test_initialize_config_new_file(self, tmp_path):
        """Test initializing a new config file."""
        config_file = tmp_path / "new-config.yml"
        
        created_path = ConfigManager.initialize_config(config_file, overwrite=False)
        
        assert created_path == config_file
        assert config_file.exists()
        
        # Verify it contains default values
        content = config_file.read_text()
        assert "default_python_version" in content
        assert "default_template" in content
    
    def test_initialize_config_existing_file(self, tmp_path):
        """Test initializing config when file already exists."""
        config_file = tmp_path / "existing-config.yml"
        config_file.write_text("existing content")
        
        with pytest.raises(ConfigurationError, match="already exists"):
            ConfigManager.initialize_config(config_file, overwrite=False)
    
    def test_initialize_config_overwrite(self, tmp_path):
        """Test initializing config with overwrite."""
        config_file = tmp_path / "existing-config.yml"
        config_file.write_text("existing content")
        
        created_path = ConfigManager.initialize_config(config_file, overwrite=True)
        
        assert created_path == config_file
        content = config_file.read_text()
        assert "default_python_version" in content
        assert "existing content" not in content
    
    def test_show_config_info(self, tmp_path, monkeypatch):
        """Test showing configuration information."""
        # Create a test config
        config_file = tmp_path / ".devman.yml"
        config_file.write_text("""
default_python_version: "3.12"
author_name: "Test User"
""")
        
        monkeypatch.setenv("DEVMAN_CONFIG", str(config_file))
        
        info = ConfigManager.show_config_info()
        
        assert "config" in info
        assert "config_file" in info
        assert "search_paths" in info
        
        assert info["config"]["default_python_version"] == "3.12"
        assert info["config"]["author_name"] == "Test User"
        assert str(config_file) in info["config_file"]
        assert len(info["search_paths"]) > 0
    
    def test_show_config_info_no_config(self):
        """Test showing config info when no config file exists."""
        info = ConfigManager.show_config_info()
        
        assert "config" in info
        assert info["config"]["default_python_version"] == "3.11"  # Default
        assert "None (using defaults)" in info["config_file"]