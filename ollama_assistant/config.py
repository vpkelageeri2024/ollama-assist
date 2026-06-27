import os
import yaml
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "ollama-assist"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG = {
    "theme": "ansicyan",
    "user_name": "You",
    "code_theme": "monokai",
}


def load_config():
    if not CONFIG_FILE.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(DEFAULT_CONFIG, f)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
            return config if config else DEFAULT_CONFIG
    except Exception:
        return DEFAULT_CONFIG
