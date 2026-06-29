import subprocess
import requests
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from .logger import logger

console = Console()
REPO_API_URL = "https://api.github.com/repos/vpkelageeri2024/ollama-assist/commits/master"

def check_for_updates():
    try:
        # Get local commit hash
        local_hash_cmd = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
        if local_hash_cmd.returncode != 0:
            return  # Not a git repo or git not installed

        local_hash = local_hash_cmd.stdout.strip()

        # Get remote commit hash
        response = requests.get(REPO_API_URL, timeout=3)
        if response.status_code == 200:
            remote_hash = response.json().get("sha")
            
            if remote_hash and local_hash != remote_hash:
                console.print(Panel("[bold yellow]🚀 A new update is available for Ollama Assistant![/bold yellow]", border_style="yellow"))
                if Confirm.ask("Would you like to automatically download and install it now?"):
                    console.print("[cyan]Pulling latest changes from GitHub...[/cyan]")
                    pull_result = subprocess.run(["git", "pull"], capture_output=True, text=True)
                    if pull_result.returncode != 0:
                        console.print(f"[red]Failed to pull updates: {pull_result.stderr}[/red]")
                        return
                        
                    console.print("[cyan]Installing dependencies...[/cyan]")
                    pip_result = subprocess.run(["pip", "install", "--user", "-e", ".", "--break-system-packages"], capture_output=True, text=True)
                    
                    console.print("[bold green]✅ Update successful! Please restart the application to apply changes.[/bold green]")
                    import sys
                    sys.exit(0)
    except Exception as e:
        logger.debug(f"Failed to check for updates: {e}")
