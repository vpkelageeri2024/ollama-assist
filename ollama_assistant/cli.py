import argparse
import sys
import platform
import psutil
import time
import re
import subprocess
from datetime import datetime
from pathlib import Path

import ollama
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.prompt import IntPrompt, Confirm
from rich.align import Align
from rich.rule import Rule
from rich.text import Text
from rich.progress import Progress
from rich.tree import Tree
from rich import box
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.python import PythonLexer

import pyperclip

from .config import load_config
from .history import load_history, save_message, clear_history, get_sessions
from .search import search_web

console = Console()

# Global state

from .state import state
from .commands import handle_slash_command
from .updater import check_for_updates
from .utils import get_model_name, print_models_table


from .logger import logger

def print_error(message):
    logger.error(message)


def get_gradient_text(text, colors):
    rich_text = Text()
    chunk_size = max(1, len(text) // len(colors))
    for i, char in enumerate(text):
        color_idx = min(i // chunk_size, len(colors) - 1)
        rich_text.append(char, style=colors[color_idx])
    return rich_text


def print_welcome_banner(model_name):
    colors = ["#00f2fe", "#4facfe", "#00f2fe", "#4facfe", "#00f2fe"]
    
    ascii_logo = """
   ____  __    __                         ___              _     __ 
  / __ \/ /   / /___ _____ ___  ____ _   /   |  __________(_)___/ /_
 / / / / /   / / __ `/ __ `__ \/ __ `/  / /| | / ___/ ___/ / ___/ __/
/ /_/ / /___/ / /_/ / / / / / / /_/ /  / ___ |(__  |__  ) /__  / /_ 
\____/_____/_/\__,_/_/ /_/ /_/\__,_/  /_/  |_/____/____/_/____/\__/ 
"""
    title = get_gradient_text(ascii_logo, colors)
    
    banner_text = Text.from_markup(f"""
[dim italic]An elite terminal experience powered by local LLMs[/dim italic]

╭─────────────────────────────────────────────────────────╮
│  [bold cyan]Active Model:[/bold cyan]  [bold yellow]{model_name:<15}[/bold yellow]                    │
│  [bold cyan]Workspace:[/bold cyan]     [bold green]{state.current_session:<15}[/bold green]                    │
╰─────────────────────────────────────────────────────────╯

[bold]⚡ Active Subsystems:[/bold]
[bold green]✓[/bold green] [dim]Real-time Token Speed[/dim]   [bold green]✓[/bold green] [dim]Native Code Execution[/dim]
[bold green]✓[/bold green] [dim]DuckDuckGo Web Search[/dim]   [bold green]✓[/bold green] [dim]Git Diff Integration[/dim]
[bold green]✓[/bold green] [dim]Local Vector RAG DB[/dim]     [bold green]✓[/bold green] [dim]Virtual Workspaces[/dim]
""")
    
    panel = Panel(
        Align.center(banner_text), 
        title="[bold blue]v2.0[/bold blue]", 
        title_align="right",
        border_style="cyan", 
        expand=False,
        padding=(1, 4)
    )
    
    console.print()
    console.print(Align.center(title))
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


def bottom_toolbar():
    return f" 🤖 Model: {state.current_model_name}  |  📂 WS: {state.current_session}  |  ⌨️  Alt+Enter: Newline  |  💡 /help  |  🛑 exit "


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



def main():
    config = load_config()
    user_name = config.get("user_name", "You")
    theme_color = config.get("theme", "cyan")
    if theme_color.startswith("ansi"):
        theme_color = theme_color[4:]

    parser = argparse.ArgumentParser(description="Ollama Assistant CLI")
    parser.add_argument("-m", "--model", type=str, help="Ollama model to use")
    parser.add_argument("-s", "--system", type=str, help="System prompt")
    parser.add_argument("-f", "--file", type=str, help="Attach a file or directory to the context")
    parser.add_argument(
        "-w", "--workspace", type=str, default="default", help="Workspace session name"
    )
    parser.add_argument("prompt", type=str, nargs="*", help="Initial prompt")
    parser.add_argument("--raw", action="store_true", help="Output raw text/JSON without UI")
    parser.add_argument("--voice", action="store_true", help="Enable text-to-speech")

    args = parser.parse_args()

    model_name = args.model
    system_prompt = args.system
    file_context = args.file
    state.current_session = args.workspace
    state.raw_mode = args.raw
    state.voice_enabled = args.voice
    initial_prompt = " ".join(args.prompt) if args.prompt else None

    if not model_name:
        try:
            available_models = ollama.list()
            models_list = (
                getattr(available_models, "models", [])
                if hasattr(available_models, "models")
                else available_models.get("models", [])
            )

            if not models_list:
                print_error(
                    "No local models found. Please pull a model first (e.g. 'ollama pull llama3')"
                )
                sys.exit(1)

            if len(models_list) == 1:
                model_name = get_model_name(models_list[0])
            else:
                print_models_table(models_list, title="Select an Ollama Model")
                choice = IntPrompt.ask(
                    "[bold cyan]Enter the number of the model to use[/bold cyan]",
                    choices=[str(i + 1) for i in range(len(models_list))],
                    show_choices=False,
                )
                model_name = get_model_name(models_list[choice - 1])

        except Exception as e:
            print_error(f"Could not connect to Ollama to list models.\n{e}")
            sys.exit(1)
    else:
        try:
            ollama.show(model_name)
        except Exception as e:
            print_error(f"Model '{model_name}' not found or Ollama is not running.")
            sys.exit(1)

    state.current_model_name = model_name
    messages = load_history(state.current_session)

    if system_prompt and (not messages or messages[0].get("role") != "system"):
        messages.insert(0, {"role": "system", "content": system_prompt})
        save_message("system", system_prompt, state.current_session)

    bindings = KeyBindings()

    @bindings.add("enter")
    def _(event):
        event.current_buffer.validate_and_handle()

    @bindings.add("escape", "enter")
    def _(event):
        event.current_buffer.insert_text("\n")

    style = Style.from_dict(
        {
            "prompt": f"{theme_color} bold",
            "bottom-toolbar": "bg:#222222 #dddddd",
        }
    )

    slash_commands = [
        "/search",
        "/model",
        "/models",
        "/pull",
        "/copy",
        "/paste",
        "/clear",
        "/save",
        "/export",
        "/help",
        "/run",
        "/commit",
        "/new",
        "/chats",
        "/load",
        "/sysinfo",
        "/stats",
        "/format",
        "/lint",
        "/logs",
        "/imagine",
        "/agent",
        "/agents",
        "/ingest",
        "/ask",
        "/cd",
        "/ls",
        "/pwd",
        "/import_openai",
        "exit",
        "quit",
    ]
    completer = WordCompleter(slash_commands, ignore_case=True)

    session = PromptSession(
        style=style,
        key_bindings=bindings,
        multiline=True,
        completer=completer,
        lexer=PygmentsLexer(PythonLexer),
        bottom_toolbar=bottom_toolbar,
    )

    if not state.raw_mode:
        print_welcome_banner(model_name)
        check_for_updates()

    if file_context:
        path = Path(file_context)
        if path.is_dir():
            tree = Tree(f"[bold cyan]📁 {path.name}[/bold cyan]")
            build_tree(path, tree)
            console.print(
                Panel(
                    tree,
                    title="[bold cyan]Attached Directory Structure[/bold cyan]",
                    border_style="cyan",
                )
            )

            # Read files for LLM context (basic implementation)
            text_content = ""
            try:
                for p in path.rglob("*"):
                    if (
                        p.is_file()
                        and not p.name.startswith(".")
                        and "node_modules" not in p.parts
                        and "__pycache__" not in p.parts
                    ):
                        try:
                            with open(p, "r") as f:
                                text_content += (
                                    f"\n--- {p} ---\n{f.read()[:5000]}\n"  # limit per file
                                )
                        except Exception as e:
                            print_error(f'Error reading {p}: {e}')
                            pass
            except Exception as e:
                print_error(f'Error reading file context: {e}')
                pass

            msg = f"Here is the context of directory {file_context}:\n```\n{text_content}\n```"
            if initial_prompt:
                msg += f"\n\n{initial_prompt}"
            handle_turn(msg, messages, state.current_model_name, config)
            initial_prompt = None

        elif path.is_file():
            try:
                with open(path, "r") as f:
                    content = f.read()
                msg = f"Here is the content of {file_context}:\n\n```\n{content}\n```"
                if initial_prompt:
                    msg += f"\n\n{initial_prompt}"
                console.print(Panel(f"📎 Attached file: {file_context}", border_style="cyan"))
                handle_turn(msg, messages, state.current_model_name, config)
                initial_prompt = None
            except Exception as e:
                print_error(f"Error reading file {file_context}: {e}")

    if initial_prompt:
        if not state.raw_mode:
            timestamp = datetime.now().strftime("%H:%M")
            console.print(f"[{theme_color} bold]{user_name}:[/] {initial_prompt} [dim]({timestamp})[/dim]")
        handle_turn(initial_prompt, messages, state.current_model_name, config)
        if state.raw_mode:
            sys.exit(0)

    if state.raw_mode:
        sys.exit(0)

    while True:
        try:
            user_input = session.prompt([("class:prompt", f"{user_name}: ")])
            if user_input.strip().lower() in ["exit", "quit"]:
                break
            if not user_input.strip():
                continue

            sys.stdout.write("\033[F\033[K")
            sys.stdout.flush()
            timestamp = datetime.now().strftime("%H:%M")
            console.print(Panel(user_input, title=f"[{theme_color} bold]{user_name}[/] [dim]({timestamp})[/dim]", box=box.ROUNDED, border_style=theme_color, title_align="right"))

            console.print(Rule(style="dim cyan"))

            if user_input.startswith("/"):
                parts = user_input.split(" ", 1)
                cmd = parts[0].lower()
                cmd_args = parts[1] if len(parts) > 1 else ""

                if cmd == "/search":
                    with console.status(
                        "[bold yellow]🌐 Searching the web...[/bold yellow]", spinner="dots"
                    ):
                        results = search_web(cmd_args)
                    preview = results[:300] + "..." if len(results) > 300 else results
                    console.print(
                        Panel(
                            preview,
                            title="[bold yellow]🔍 Search Results[/bold yellow]",
                            border_style="yellow",
                        )
                    )
                    augmented_prompt = f"Please answer the user's query based on these web search results:\n\n{results}\n\nUser Query: {cmd_args}"
                    handle_turn(
                        augmented_prompt,
                        messages,
                        state.current_model_name,
                        config,
                        display_input=cmd_args,
                    )
                    console.print(Rule(style="dim cyan"))
                    continue

                elif cmd == "/pull":
                    if not cmd_args:
                        print_error("Please specify a model to pull. e.g. /pull llama3")
                        continue
                    with Progress() as progress:
                        task = progress.add_task(f"[cyan]Downloading {cmd_args}...", total=100)
                        try:
                            for response in ollama.pull(cmd_args, stream=True):
                                if "total" in response and "completed" in response:
                                    progress.update(
                                        task,
                                        completed=response["completed"],
                                        total=response["total"],
                                    )
                                elif "status" in response:
                                    progress.update(task, description=f"[cyan]{response['status']}")
                            console.print(
                                f"[bold green]✅ Successfully pulled {cmd_args}![/bold green]"
                            )
                        except Exception as e:
                            print_error(f"Failed to pull {cmd_args}: {e}")
                    console.print(Rule(style="dim cyan"))
                    continue

                elif cmd == "/copy":
                    if state.last_assistant_response:
                        pyperclip.copy(state.last_assistant_response)
                        console.print(
                            "[bold green]📋 ✅ Copied last assistant response to clipboard![/bold green]"
                        )
                    else:
                        print_error("Nothing to copy yet!")
                    console.print(Rule(style="dim cyan"))
                    continue

                elif cmd == "/help":
                    print_help()
                    console.print(Rule(style="dim cyan"))
                    continue

                else:
                    handled, state.current_model_name = handle_slash_command(cmd, cmd_args, state.current_model_name, messages, config, handle_turn)
                    if handled:
                        console.print(Rule(style="dim cyan"))
                        continue

            handle_turn(user_input, messages, state.current_model_name, config)
            console.print(Rule(style="dim cyan"))

        except (KeyboardInterrupt, EOFError):
            break

    console.print(
        Panel(
            "[bold green]Goodbye! Keep building awesome things.[/bold green]",
            border_style="green",
            expand=False,
        )
    )


def handle_turn(user_input: str, messages: list, model_name: str, config: dict, display_input: str = None):
    messages.append({"role": "user", "content": user_input})
    save_message("user", user_input, state.current_session)

    if not state.raw_mode:
        timestamp = datetime.now().strftime("%H:%M")
        if display_input:
            console.print(f"[cyan bold]{config.get('user_name', 'You')} (Search):[/] {display_input} [dim]({timestamp})[/dim]")
    
    try:
        response_stream = ollama.chat(model=model_name, messages=messages, stream=True)
        full_response = ""
        start_time = time.time()
        tokens = 0

        if state.raw_mode:
            for chunk in response_stream:
                content = chunk["message"]["content"]
                full_response += content
                sys.stdout.write(content)
                sys.stdout.flush()
            sys.stdout.write("\n")
        else:
            with Live(console=console, refresh_per_second=15) as live:
                for chunk in response_stream:
                    content = chunk["message"]["content"]
                    full_response += content
                    tokens += 1
                    elapsed = time.time() - start_time
                    speed = tokens / elapsed if elapsed > 0 else 0
                    
                    display_md = Markdown(full_response + "█", code_theme=config.get("code_theme", "monokai"))
                    panel = Panel(display_md, title=f"[bold magenta]🤖 Assistant[/bold magenta] [dim]({timestamp})[/dim] | [yellow]⚡ {speed:.1f} t/s[/yellow]", title_align="left", border_style="magenta")
                    live.update(panel)

                final_md = Markdown(full_response, code_theme=config.get("code_theme", "monokai"))
                final_panel = Panel(final_md, title=f"[bold magenta]🤖 Assistant[/bold magenta] [dim]({timestamp})[/dim] | [yellow]⚡ {(tokens/(time.time()-start_time)):.1f} t/s[/yellow]", title_align="left", border_style="magenta")
                live.update(final_panel)

        messages.append({"role": "assistant", "content": full_response})
        save_message("assistant", full_response, state.current_session)
        state.last_assistant_response = full_response
        
        if state.voice_enabled:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(full_response)
                engine.runAndWait()
            except Exception as e:
                if not state.raw_mode:
                    print_error(f"TTS error: {e}")

        if not state.raw_mode and (time.time() - start_time) > 5.0:
            try:
                subprocess.run(["notify-send", "Ollama Assistant", "Generation Complete!"], capture_output=True)
            except Exception:
                pass

    except Exception as e:
        if not state.raw_mode:
            print_error(f"Communicating with Ollama: {e}")
        else:
            print(f"Error: {e}")
