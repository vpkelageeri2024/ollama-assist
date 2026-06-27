from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich.tree import Tree
from pathlib import Path

console = Console()


def print_error(message):
    console.print(
        Panel(f"[bold red]❌ ERROR:[/bold red] {message}", border_style="red", expand=False)
    )


def get_model_name(m):
    return (
        getattr(m, "model", None)
        or getattr(m, "name", None)
        or (m.get("model") if isinstance(m, dict) else None)
        or (m.get("name") if isinstance(m, dict) else str(m))
    )


def print_models_table(models_list, title="Available Local Models"):
    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("No.", style="dim", width=4, justify="center")
    table.add_column("Model Name", style="bold cyan")
    table.add_column("Parameters", style="green", justify="right")
    table.add_column("Size", style="yellow", justify="right")
    table.add_column("Quantization", style="blue", justify="right")

    for i, m in enumerate(models_list):
        name = get_model_name(m)
        details = getattr(m, "details", None)
        if not details and isinstance(m, dict):
            details = m.get("details", {})

        param_size = str(
            getattr(details, "parameter_size", None)
            or (details.get("parameter_size") if isinstance(details, dict) else "-")
        )
        quant = str(
            getattr(details, "quantization_level", None)
            or (details.get("quantization_level") if isinstance(details, dict) else "-")
        )

        size_bytes = getattr(m, "size", None) or (m.get("size") if isinstance(m, dict) else 0)
        size_gb = f"{(size_bytes / (1024**3)):.2f} GB" if size_bytes else "-"

        table.add_row(str(i + 1), name, param_size, size_gb, quant)

    panel = Panel(
        Align.center(table), title=f"[bold green]{title}[/bold green]", border_style="cyan"
    )
    console.print()
    console.print(panel)
    console.print()


def get_gradient_text(text, colors):
    rich_text = Text()
    chunk_size = max(1, len(text) // len(colors))
    for i, char in enumerate(text):
        color_idx = min(i // chunk_size, len(colors) - 1)
        rich_text.append(char, style=colors[color_idx])
    return rich_text


def print_welcome_banner(model_name, current_session):
    colors = ["#ff0055", "#ff00aa", "#cc00ff", "#5500ff", "#0055ff", "#00aaff"]
    title = get_gradient_text("████████ OLLAMA ASSISTANT CLI ████████", colors)

    banner_text = Text.from_markup(f"""
[dim]Premium Terminal UI powered by local LLMs[/dim]

[green]Active Model:[/green] [bold yellow]{model_name}[/bold yellow]
[green]Workspace:[/green]    [bold yellow]{current_session}[/bold yellow]

[bold]Features Active:[/bold]
[cyan]✓[/cyan] Token Speed Meter  [cyan]✓[/cyan] Code Execution
[cyan]✓[/cyan] Web Search         [cyan]✓[/cyan] Git Integration
[cyan]✓[/cyan] Workspaces         [cyan]✓[/cyan] Directory Trees
""")
    panel = Panel(Align.center(banner_text), title=title, border_style="magenta", expand=False)
    console.print(Align.center(panel))
    console.print()


def print_help():
    help_text = """
[bold yellow]/run[/bold yellow]             - Execute the last generated code block (Jupyter style)
[bold yellow]/format[/bold yellow]          - Auto-format the last python code block (Black)
[bold yellow]/lint[/bold yellow]            - Run Flake8 on the last python code block
[bold yellow]/paste[/bold yellow]           - Grab clipboard contents and send to Assistant
[bold yellow]/sysinfo[/bold yellow]         - Show gorgeous system hardware stats
[bold yellow]/stats[/bold yellow]           - Show analytics for the current workspace
[bold yellow]/logs[/bold yellow]            - Analyze recent system logs for errors
[bold yellow]/commit[/bold yellow]          - Read git diff and generate commit msg
[bold yellow]/search <query>[/bold yellow]  - Search the web and read results
[bold yellow]/imagine <query>[/bold yellow] - Generate an image using local API
[bold yellow]/agent <task>[/bold yellow]    - Launch an autonomous ReAct loop to solve a task
[bold yellow]/ingest <dir>[/bold yellow]    - Load a folder into the Local Vector Database (RAG)
[bold yellow]/ask <query>[/bold yellow]      - Search the Vector DB and answer question
[bold yellow]/cd, /ls, /pwd[/bold yellow]   - Navigate the file system natively
[bold yellow]/import_openai[/bold yellow]  - Import ChatGPT history from conversations.json
[bold yellow]/new <name>[/bold yellow]      - Start a new workspace/chat
[bold yellow]/load <name>[/bold yellow]     - Load a previous workspace
[bold yellow]/chats[/bold yellow]           - List all workspaces
[bold yellow]/model <name>[/bold yellow]    - Switch active model mid-chat
[bold yellow]/models[/bold yellow]          - List all downloaded local models
[bold yellow]/pull <name>[/bold yellow]     - Download a new model (with progress)
[bold yellow]/copy[/bold yellow]            - Copy the last response to clipboard
[bold yellow]/clear[/bold yellow]           - Wipe the conversation history
[bold yellow]/save <file>[/bold yellow]     - Export the chat to a markdown file
[bold yellow]/export <file>[/bold yellow]   - Export the chat to a beautiful HTML file
    """
    console.print(
        Panel(
            help_text,
            title="[bold cyan]💡 Keyboard & Command Shortcuts[/bold cyan]",
            border_style="cyan",
            expand=False,
        )
    )


def bottom_toolbar(current_model_name, current_session):
    return f" 🤖 Model: {current_model_name}  |  📂 WS: {current_session}  |  ⌨️  Alt+Enter: Newline  |  💡 /help  |  🛑 exit "


def build_tree(directory, tree):
    try:
        paths = sorted(Path(directory).iterdir(), key=lambda x: (x.is_file(), x.name))
        for path in paths:
            if path.name.startswith(".") or path.name == "__pycache__":
                continue
            if path.is_dir():
                branch = tree.add(f"[bold cyan]📁 {path.name}[/bold cyan]")
                build_tree(path, branch)
            else:
                tree.add(f"[green]📄 {path.name}[/green]")
    except PermissionError:
        tree.add("[red]Permission Denied[/red]")
