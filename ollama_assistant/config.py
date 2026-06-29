import os
import yaml
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm

CONFIG_DIR = Path.home() / ".config" / "ollama-assist"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG = {
    "theme": "cyan",
    "user_name": "You",
    "code_theme": "monokai",
    "personas": {
        "coding_expert": "You are a senior software engineer. Answer with minimal fluff and highly optimized code.",
        "pirate": "You are a grumpy pirate. Answer all questions in pirate slang."
    }
}

def interactive_wizard():
    console = Console()
    console.print("[bold magenta]✨ Welcome to Ollama Assistant Setup! ✨[/bold magenta]")
    console.print("Let's configure your terminal AI experience.\n")
    
    user_name = Prompt.ask("[cyan]What should I call you?[/cyan]", default="You")
    theme = Prompt.ask("[cyan]Choose a UI theme color (e.g., ansicyan, green, magenta, red)[/cyan]", default="ansicyan")
    
    config = DEFAULT_CONFIG.copy()
    config["user_name"] = user_name
    config["theme"] = theme
    
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f)
        
    console.print("[bold green]✅ Configuration saved! Starting assistant...[/bold green]\n")
    return config

def load_config():
    if not CONFIG_FILE.exists():
        return interactive_wizard()
    try:
        with open(CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
            return config if config else DEFAULT_CONFIG
    except Exception:
        return DEFAULT_CONFIG
