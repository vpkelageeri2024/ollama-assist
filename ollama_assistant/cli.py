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
current_model_name = "None"
last_assistant_response = ""
current_session = "default"
run_globals = {}


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


def print_welcome_banner(model_name):
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


def bottom_toolbar():
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


def handle_slash_command(command, args, model_name, messages, config):
    global current_model_name, current_session

    if command == "/clear":
        if Confirm.ask(
            "[bold red]Are you sure you want to clear the conversation history?[/bold red]"
        ):
            clear_history(current_session)
            messages.clear()
            console.print(
                Panel(
                    "[bold green]🗑️ Conversation history cleared![/bold green]",
                    border_style="green",
                    expand=False,
                )
            )
        return True, model_name

    elif command == "/models":
        try:
            available_models = ollama.list()
            models_list = (
                getattr(available_models, "models", [])
                if hasattr(available_models, "models")
                else available_models.get("models", [])
            )
            print_models_table(models_list, title="Local Models")
        except Exception as e:
            print_error(f"Failed to fetch models: {e}")
        return True, model_name

    elif command == "/model":
        if args:
            new_model = args.strip()
            current_model_name = new_model
            console.print(
                Panel(
                    f"[bold green]🔄 Switched active model to:[/bold green] [bold yellow]{new_model}[/bold yellow]",
                    border_style="green",
                    expand=False,
                )
            )
            return True, new_model
        else:
            print_error("Please specify a model name (e.g. /model phi3)")
            return True, model_name

    elif command == "/save":
        if args:
            filename = args.strip()
            try:
                with open(filename, "w") as f:
                    for msg in messages:
                        f.write(f"### {msg['role'].capitalize()}\n{msg['content']}\n\n")
                console.print(
                    Panel(
                        f"[bold green]💾 ✅ Conversation successfully saved to:[/bold green] {filename}",
                        border_style="green",
                        expand=False,
                    )
                )
            except Exception as e:
                print_error(f"Failed to save: {e}")
        else:
            print_error("Please specify a filename (e.g. /save chat.md)")
        return True, model_name

    elif command == "/export":
        filename = args.strip() or f"chat_export_{int(time.time())}.html"
        try:
            import markdown

            html_content = "<html><head><style>body { font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #1e1e1e; color: #f4f4f4; } .user { color: #00aaff; margin-bottom: 20px; } .assistant { color: #ff00aa; margin-bottom: 20px; } pre { background: #000; padding: 10px; border-radius: 5px; overflow-x: auto; }</style></head><body>"
            html_content += f"<h1>Ollama Assistant Export ({current_session})</h1>"
            for msg in messages:
                role_class = msg["role"]
                content = markdown.markdown(
                    msg["content"], extensions=["fenced_code", "codehilite"]
                )
                html_content += f"<div class='{role_class}'><h3 style='text-transform: capitalize;'>{role_class}</h3>{content}</div><hr>"
            html_content += "</body></html>"
            with open(filename, "w") as f:
                f.write(html_content)
            console.print(
                Panel(
                    f"[bold green]🌐 ✅ Exported chat to HTML:[/bold green] {filename}",
                    border_style="green",
                    expand=False,
                )
            )
        except ImportError:
            print_error("The 'markdown' package is not installed. Run 'pip install markdown'")
        except Exception as e:
            print_error(f"Failed to export: {e}")
        return True, model_name

    elif command == "/new":
        current_session = args.strip() or f"session_{int(time.time())}"
        messages.clear()
        messages.extend(load_history(current_session))
        console.print(f"[bold green]📂 Started new workspace:[/bold green] {current_session}")
        return True, model_name

    elif command == "/load":
        if args:
            current_session = args.strip()
            messages.clear()
            messages.extend(load_history(current_session))
            console.print(f"[bold green]📂 Loaded workspace:[/bold green] {current_session}")
        else:
            print_error("Specify a workspace name")
        return True, model_name

    elif command == "/chats":
        sessions = get_sessions()
        console.print("[bold cyan]Available Workspaces:[/bold cyan]")
        for s in sessions:
            mark = "★" if s == current_session else " "
            console.print(f"  [yellow]{mark}[/yellow] {s}")
        return True, model_name

    elif command == "/run":
        if not last_assistant_response:
            print_error("No response available to run.")
            return True, model_name

        blocks = re.findall(r"```(python|bash|sh)\n(.*?)```", last_assistant_response, re.DOTALL)
        if not blocks:
            print_error("No executable code blocks (python/bash) found in the last response.")
            return True, model_name

        lang, code = blocks[-1]
        console.print(Panel(code, title=f"[{lang}] Code to execute", border_style="yellow"))
        if Confirm.ask("[bold red]⚠️ Execute this code on your machine?[/bold red]"):
            try:
                if lang == "python":
                    import io
                    import contextlib

                    out_buf = io.StringIO()
                    with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(out_buf):
                        exec(code, run_globals)
                    out = out_buf.getvalue()
                else:
                    result = subprocess.run(["bash", "-c", code], capture_output=True, text=True)
                    out = result.stdout + result.stderr

                console.print(
                    Panel(out, title="[bold green]Output[/bold green]", border_style="green")
                )

                if Confirm.ask("Send output back to the assistant?"):
                    handle_turn(
                        f"I ran the code. Here is the output:\n```\n{out}\n```",
                        messages,
                        model_name,
                        config,
                    )
            except Exception as e:
                print_error(str(e))
        return True, model_name

    elif command == "/commit":
        try:
            diff = subprocess.check_output(
                ["git", "diff", "HEAD"], stderr=subprocess.STDOUT
            ).decode("utf-8")
            if not diff:
                console.print("[yellow]No changes to commit.[/yellow]")
                return True, model_name
            prompt = f"Write a concise, professional git commit message for the following diff. Do not explain, just output the commit message:\n\n```diff\n{diff}\n```"
            handle_turn(
                prompt,
                messages,
                model_name,
                config,
                display_input="Generate git commit message for current changes",
            )
        except subprocess.CalledProcessError:
            print_error("Not a git repository or git is not installed.")
        except Exception as e:
            print_error(f"Git error: {e}")
        return True, model_name

    elif command == "/cd":
        path = args.strip()
        if path:
            try:
                import os

                os.chdir(path)
                console.print(f"[green]Changed directory to: {os.getcwd()}[/green]")
            except Exception as e:
                print_error(str(e))
        return True, model_name
    elif command == "/ls":
        try:
            import os

            files = os.listdir(".")
            console.print(Panel("\n".join(files), title=f"[cyan]Contents of {os.getcwd()}[/cyan]"))
        except Exception as e:
            print_error(str(e))
        return True, model_name
    elif command == "/pwd":
        import os

        console.print(f"[cyan]{os.getcwd()}[/cyan]")
        return True, model_name

    elif command == "/imagine":
        query = args.strip()
        if not query:
            print_error("Please provide a prompt for the image.")
            return True, model_name

        with console.status(
            f"[bold yellow]🎨 Generating image for '{query}'...[/bold yellow]", spinner="dots"
        ):
            import requests
            from urllib.parse import quote

            safe_query = quote(query)
            url = f"https://image.pollinations.ai/prompt/{safe_query}"
            try:
                r = requests.get(url)
                r.raise_for_status()
                filename = f"generated_image_{int(time.time())}.jpg"
                with open(filename, "wb") as f:
                    f.write(r.content)
                console.print(
                    Panel(
                        f"[bold green]✅ Image successfully generated and saved to:[/bold green] {filename}",
                        border_style="green",
                        expand=False,
                    )
                )
            except Exception as e:
                print_error(f"Failed to generate image: {e}")
        return True, model_name

    elif command == "/import_openai":
        file_path = args.strip()
        if not file_path:
            print_error("Please provide path to conversations.json")
            return True, model_name

        try:
            import json

            with open(file_path, "r") as f:
                data = json.load(f)

            imported = 0
            for conv in data:
                title = conv.get("title", "Imported")
                session_name = f"openai_{title.replace(' ', '_')[:20]}_{int(time.time())}"
                mapping = conv.get("mapping", {})
                for node_id, node in mapping.items():
                    if (
                        node.get("message")
                        and node["message"].get("content")
                        and node["message"]["content"].get("parts")
                    ):
                        role = node["message"]["author"]["role"]
                        parts = node["message"]["content"]["parts"]
                        text = "".join(str(p) for p in parts if isinstance(p, str))
                        if text:
                            save_message(role, text, session_name)
                imported += 1
            console.print(
                f"[bold green]✅ Imported {imported} conversations from ChatGPT![/bold green]"
            )
        except Exception as e:
            print_error(f"Import failed: {e}")
        return True, model_name

    elif command == "/ingest":
        directory = args.strip()
        if not directory or not Path(directory).is_dir():
            print_error("Please provide a valid directory path.")
            return True, model_name

        with console.status("[bold yellow]📚 Ingesting documents into Vector DB...[/bold yellow]"):
            try:
                import chromadb
                import warnings

                warnings.filterwarnings("ignore")
                db_path = str(Path.home() / ".config" / "ollama-assist" / "chroma_db")
                chroma_client = chromadb.PersistentClient(path=db_path)
                collection = chroma_client.get_or_create_collection(name="local_docs")

                count = 0
                for p in Path(directory).rglob("*"):
                    if p.is_file() and not p.name.startswith(".") and "node_modules" not in p.parts:
                        try:
                            with open(p, "r", encoding="utf-8") as f:
                                text = f.read()
                            chunk_size = 1000
                            chunks = [
                                text[i : i + chunk_size] for i in range(0, len(text), chunk_size)
                            ]
                            for i, chunk in enumerate(chunks):
                                doc_id = f"{p.name}_{count}_{i}"
                                collection.add(
                                    documents=[chunk], metadatas=[{"source": str(p)}], ids=[doc_id]
                                )
                            count += 1
                        except:
                            pass
                console.print(
                    Panel(
                        f"[bold green]✅ Ingested {count} files into the local Vector Database![/bold green]",
                        border_style="green",
                        expand=False,
                    )
                )
            except Exception as e:
                print_error(str(e))
        return True, model_name

    elif command == "/ask":
        query = args.strip()
        if not query:
            print_error("Please provide a question.")
            return True, model_name

        with console.status("[bold yellow]🔍 Searching local documents...[/bold yellow]"):
            try:
                import chromadb
                import warnings

                warnings.filterwarnings("ignore")
                db_path = str(Path.home() / ".config" / "ollama-assist" / "chroma_db")
                chroma_client = chromadb.PersistentClient(path=db_path)
                collection = chroma_client.get_or_create_collection(name="local_docs")

                results = collection.query(query_texts=[query], n_results=3)

                context = ""
                if results["documents"] and results["documents"][0]:
                    for i, doc in enumerate(results["documents"][0]):
                        meta = results["metadatas"][0][i]
                        context += f"\n--- Source: {meta.get('source', 'Unknown')} ---\n{doc}\n"

                console.print(
                    Panel(context, title="[cyan]Retrieved Context[/cyan]", border_style="cyan")
                )

                prompt = f"Answer the user's question based ONLY on the following retrieved local documents:\n\n{context}\n\nQuestion: {query}"
                handle_turn(prompt, messages, model_name, config, display_input=f"Ask RAG: {query}")
            except Exception as e:
                print_error(str(e))
        return True, model_name

    elif command in ["/agent", "/agents"]:
        task = args.strip()
        if not task:
            print_error("Please provide a task for the agent.")
            return True, model_name

        agent_messages = [
            {
                "role": "system",
                "content": "You are a terminal execution agent. YOU HAVE REAL TERMINAL ACCESS. Your ONLY purpose is to output executable code blocks. Do not act like an AI model. Do not apologize.\nTo execute a command, output a ```bash\n<command>\n``` block. \nWhen the task is fully complete, output exactly 'DONE' by itself on the last line.\n\nEXAMPLE:\nUser: Task: find my username\nAssistant:\n```bash\nwhoami\n```\nUser: Execution Output:\n```\nvishal\n```\nAssistant:\nThe username is vishal.\nDONE",
            },
            {"role": "user", "content": f"Task: {task}"},
        ]

        console.print(
            Panel(
                f"[bold magenta]🤖 Autonomous Agent Loop Started:[/bold magenta] {task}\n[dim]The agent will think and execute iteratively.[/dim]",
                border_style="magenta",
            )
        )

        iteration = 0
        max_iterations = 10

        while iteration < max_iterations:
            iteration += 1
            console.print(f"\n[dim]--- Iteration {iteration} ---[/dim]")

            try:
                with console.status(
                    "[bold magenta]Agent is thinking...[/bold magenta]", spinner="dots"
                ):
                    response = ollama.chat(model=model_name, messages=agent_messages)
                    content = response.get("message", {}).get("content", "")

                console.print(
                    Panel(content, title="[cyan]Agent Thought[/cyan]", border_style="cyan")
                )
                agent_messages.append({"role": "assistant", "content": content})

                if content.strip().endswith("DONE"):
                    console.print("[bold green]✅ Agent declared the task COMPLETE![/bold green]")
                    break

                blocks = re.findall(r"```(bash|sh|python)\n(.*?)```", content, re.DOTALL)
                if not blocks:
                    console.print(
                        "[yellow]No executable code found. Asking agent to proceed...[/yellow]"
                    )
                    agent_messages.append(
                        {
                            "role": "user",
                            "content": "CRITICAL INSTRUCTION: You failed to provide a code block. DO NOT apologize. DO NOT act like an AI. You MUST provide a ```bash``` or ```python``` block to execute, or output 'DONE' if the task is finished.",
                        }
                    )
                    continue

                lang, code = blocks[-1]
                console.print(
                    Panel(code, title=f"[yellow]Executing {lang}[/yellow]", border_style="yellow")
                )

                if lang == "python":
                    result = subprocess.run(["python3", "-c", code], capture_output=True, text=True)
                else:
                    result = subprocess.run(["bash", "-c", code], capture_output=True, text=True)

                out = result.stdout + result.stderr
                if not out:
                    out = "<Command executed silently with no output>"

                console.print(
                    Panel(
                        out[:1000] + ("..." if len(out) > 1000 else ""),
                        title="[green]Execution Output[/green]",
                        border_style="green",
                    )
                )

                agent_messages.append(
                    {
                        "role": "user",
                        "content": f"Execution Output:\n```\n{out}\n```\nWhat is the next step? (Output a code block or DONE)",
                    }
                )

            except Exception as e:
                print_error(f"Agent Loop Error: {e}")
                break

        if iteration >= max_iterations:
            console.print(
                "[bold red]❌ Agent reached maximum iterations (10) and was forcefully stopped.[/bold red]"
            )

        return True, model_name

    elif command == "/sysinfo":
        uname = platform.uname()
        mem = psutil.virtual_memory()
        info = f"""
[bold cyan]System Information[/bold cyan]
[green]OS:[/green] {uname.system} {uname.release}
[green]Node:[/green] {uname.node}
[green]Processor:[/green] {uname.processor}
[green]RAM:[/green] {mem.used / (1024**3):.1f} GB / {mem.total / (1024**3):.1f} GB ({mem.percent}%)
[green]Active Model:[/green] {model_name}
        """
        console.print(Panel(info, border_style="cyan", expand=False))
        return True, model_name

    elif command == "/stats":
        total_msgs = len(messages)
        user_chars = sum(len(m["content"]) for m in messages if m["role"] == "user")
        asst_chars = sum(len(m["content"]) for m in messages if m["role"] == "assistant")
        sys_chars = sum(len(m["content"]) for m in messages if m["role"] == "system")

        stat_panel = f"""
[bold cyan]Workspace Analytics ({current_session})[/bold cyan]
[white]Total Messages:[/white] {total_msgs}
[green]User Input:[/green] {user_chars} characters
[magenta]Assistant Output:[/magenta] {asst_chars} characters
[dim]System Prompts: {sys_chars} characters[/dim]
        """
        console.print(Panel(stat_panel, border_style="cyan", expand=False))
        return True, model_name

    elif command == "/paste":
        content = pyperclip.paste()
        if not content:
            print_error("Clipboard is empty.")
            return True, model_name

        preview = content[:500] + ("..." if len(content) > 500 else "")
        console.print(Panel(preview, title="[cyan]📋 Pasted from Clipboard[/cyan]"))
        prompt = f"Please analyze or respond to the following pasted content:\\n\\n{content}"
        handle_turn(
            prompt, messages, model_name, config, display_input="<Pasted Clipboard Content>"
        )
        return True, model_name

    elif command in ["/lint", "/format"]:
        if not last_assistant_response:
            print_error("No response available.")
            return True, model_name

        blocks = re.findall(r"```python\n(.*?)```", last_assistant_response, re.DOTALL)
        if not blocks:
            print_error("No Python code blocks found in the last response.")
            return True, model_name

        code = blocks[-1]
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write(code)
            temp_path = f.name

        try:
            if command == "/format":
                subprocess.run(["black", temp_path], capture_output=True)
                with open(temp_path, "r") as f:
                    formatted_code = f.read()
                console.print(
                    Panel(
                        f"```python\n{formatted_code}\n```",
                        title="[bold green]Formatted Code (Black)[/bold green]",
                        border_style="green",
                    )
                )
                pyperclip.copy(formatted_code)
                console.print("[dim]Copied formatted code to clipboard.[/dim]")

            elif command == "/lint":
                result = subprocess.run(["flake8", temp_path], capture_output=True, text=True)
                if result.stdout:
                    console.print(
                        Panel(
                            result.stdout,
                            title="[bold red]Lint Errors found by flake8[/bold red]",
                            border_style="red",
                        )
                    )
                    if Confirm.ask("Ask assistant to fix these errors?"):
                        prompt = f"I linted your python code and got these errors from flake8. Please fix them:\n```\n{result.stdout}\n```\n\nCode:\n```python\n{code}\n```"
                        handle_turn(
                            prompt, messages, model_name, config, display_input="Fix linting errors"
                        )
                else:
                    console.print(
                        Panel(
                            "[bold green]No linting errors found! Perfect code.[/bold green]",
                            border_style="green",
                            expand=False,
                        )
                    )
        except Exception as e:
            print_error(f"Error executing command: {e}")

        Path(temp_path).unlink()
        return True, model_name

    elif command == "/logs":
        try:
            result = subprocess.run(["dmesg", "-T"], capture_output=True, text=True)
            lines = result.stdout.split("\n")[-50:]
            logs = "\n".join(lines)
            prompt = f"Analyze these recent system logs and tell me if there are any critical errors or hardware issues:\n\n```\n{logs}\n```"
            handle_turn(prompt, messages, model_name, config, display_input="Analyze system logs")
        except Exception as e:
            print_error(f"Could not read logs: {e}")
        return True, model_name

    return False, model_name


def main():
    global current_model_name, current_session
    config = load_config()
    user_name = config.get("user_name", "You")
    theme_color = config.get("theme", "ansicyan")

    parser = argparse.ArgumentParser(description="Ollama Assistant CLI")
    parser.add_argument("-m", "--model", type=str, help="Ollama model to use")
    parser.add_argument("-s", "--system", type=str, help="System prompt")
    parser.add_argument("-f", "--file", type=str, help="Attach a file or directory to the context")
    parser.add_argument(
        "-w", "--workspace", type=str, default="default", help="Workspace session name"
    )
    parser.add_argument("prompt", type=str, nargs="*", help="Initial prompt")

    args = parser.parse_args()

    model_name = args.model
    system_prompt = args.system
    file_context = args.file
    current_session = args.workspace
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

    current_model_name = model_name
    messages = load_history(current_session)

    if system_prompt and (not messages or messages[0].get("role") != "system"):
        messages.insert(0, {"role": "system", "content": system_prompt})
        save_message("system", system_prompt, current_session)

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

    print_welcome_banner(model_name)

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
                        except:
                            pass
            except:
                pass

            msg = f"Here is the context of directory {file_context}:\n```\n{text_content}\n```"
            if initial_prompt:
                msg += f"\n\n{initial_prompt}"
            handle_turn(msg, messages, current_model_name, config)
            initial_prompt = None

        elif path.is_file():
            try:
                with open(path, "r") as f:
                    content = f.read()
                msg = f"Here is the content of {file_context}:\n\n```\n{content}\n```"
                if initial_prompt:
                    msg += f"\n\n{initial_prompt}"
                console.print(Panel(f"📎 Attached file: {file_context}", border_style="cyan"))
                handle_turn(msg, messages, current_model_name, config)
                initial_prompt = None
            except Exception as e:
                print_error(f"Error reading file {file_context}: {e}")

    if initial_prompt:
        timestamp = datetime.now().strftime("%H:%M")
        console.print(
            f"[{theme_color} bold]{user_name}:[/] {initial_prompt} [dim]({timestamp})[/dim]"
        )
        handle_turn(initial_prompt, messages, current_model_name, config)

    while True:
        try:
            user_input = session.prompt([("class:prompt", f"{user_name}: ")])
            if user_input.strip().lower() in ["exit", "quit"]:
                break
            if not user_input.strip():
                continue

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
                        current_model_name,
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
                    if last_assistant_response:
                        pyperclip.copy(last_assistant_response)
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
                    handled, current_model_name = handle_slash_command(
                        cmd, cmd_args, current_model_name, messages, config
                    )
                    if handled:
                        console.print(Rule(style="dim cyan"))
                        continue

            handle_turn(user_input, messages, current_model_name, config)
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


def handle_turn(user_input, messages, model_name, config, display_input=None):
    global last_assistant_response, current_session
    messages.append({"role": "user", "content": user_input})
    save_message("user", user_input, current_session)

    timestamp = datetime.now().strftime("%H:%M")
    if display_input:
        console.print(
            f"[cyan bold]{config.get('user_name', 'You')} (Search):[/] {display_input} [dim]({timestamp})[/dim]"
        )

    try:
        response_stream = ollama.chat(model=model_name, messages=messages, stream=True)
        full_response = ""
        start_time = time.time()
        tokens = 0

        with Live(console=console, refresh_per_second=15) as live:
            for chunk in response_stream:
                content = chunk["message"]["content"]
                full_response += content
                tokens += 1

                elapsed = time.time() - start_time
                speed = tokens / elapsed if elapsed > 0 else 0

                display_md = Markdown(
                    full_response + "█", code_theme=config.get("code_theme", "monokai")
                )
                panel = Panel(
                    display_md,
                    title=f"[bold magenta]🤖 Assistant[/bold magenta] [dim]({timestamp})[/dim] | [yellow]⚡ {speed:.1f} t/s[/yellow]",
                    title_align="left",
                    border_style="magenta",
                )
                live.update(panel)

            final_md = Markdown(full_response, code_theme=config.get("code_theme", "monokai"))
            final_panel = Panel(
                final_md,
                title=f"[bold magenta]🤖 Assistant[/bold magenta] [dim]({timestamp})[/dim] | [yellow]⚡ {(tokens/(time.time()-start_time)):.1f} t/s[/yellow]",
                title_align="left",
                border_style="magenta",
            )
            live.update(final_panel)

        messages.append({"role": "assistant", "content": full_response})
        save_message("assistant", full_response, current_session)
        last_assistant_response = full_response

        # Send desktop notification if generation took a while
        if (time.time() - start_time) > 5.0:
            try:
                subprocess.run(
                    ["notify-send", "Ollama Assistant", "Generation Complete!"], capture_output=True
                )
            except:
                pass

    except Exception as e:
        print_error(f"Communicating with Ollama: {e}")


if __name__ == "__main__":
    main()
