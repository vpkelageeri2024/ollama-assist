import pytest
from pathlib import Path
from ollama_assistant.config import load_config, DEFAULT_CONFIG
import ollama_assistant.config

@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    config_dir = tmp_path / ".config" / "ollama-assist"
    monkeypatch.setattr(ollama_assistant.config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(ollama_assistant.config, "CONFIG_FILE", config_dir / "config.yaml")
    return config_dir

from unittest.mock import patch

def test_load_config_default(temp_config_dir):
    with patch("ollama_assistant.config.Prompt.ask", side_effect=["You", "ansicyan"]):
        config = load_config()
    assert config == DEFAULT_CONFIG

def test_load_config_existing(temp_config_dir):
    temp_config_dir.mkdir(parents=True, exist_ok=True)
    with open(temp_config_dir / "config.yaml", "w") as f:
        f.write("theme: custom\nuser_name: Bob\ncode_theme: dark")
    
    config = load_config()
    assert config["theme"] == "custom"
    assert config["user_name"] == "Bob"
