import logging
from pathlib import Path
from rich.logging import RichHandler

CONFIG_DIR = Path.home() / ".config" / "ollama-assist"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = CONFIG_DIR / "app.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        RichHandler(rich_tracebacks=True, markup=True, show_time=False, show_path=False)
    ]
)

logger = logging.getLogger("ollama-assist")
