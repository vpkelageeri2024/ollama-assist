from .utils import print_models_table
import time
import re
import subprocess
from pathlib import Path
import platform
import psutil
import pyperclip
import ollama
from rich.panel import Panel
from rich.prompt import Confirm, Prompt, IntPrompt
from .state import state
from .history import clear_history, load_history, save_message, get_sessions

# We need to import console and print_error from somewhere. 
# For now, let's just create a local console and print_error in commands.py to avoid circular imports.
from rich.console import Console
console = Console()
from .logger import logger

def print_error(message):
    logger.error(message)

# We need to pass handle_turn down if it's used inside commands.py (e.g., for /commit, /paste).
# To avoid circular imports, we can pass it as a callback or import it locally inside the function.
# The simplest is to import handle_turn locally where needed, or we can just keep it in cli.py and pass it as an argument?
# Wait, handle_slash_command doesn't take handle_turn as an argument right now. It just calls it directly.
# Let's modify handle_slash_command signature to accept handle_turn as an argument.

def handle_slash_command(command: str, args: str, model_name: str, messages: list, config: dict, handle_turn_cb) -> tuple[bool, str]:
    
    if command == "/clear":
        if Confirm.ask(
            "[bold red]Are you sure you want to clear the conversation history?[/bold red]"
        ):
            clear_history(state.current_session)
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
        if not args:
            try:
                models_list = ollama.list()["models"]
                if not models_list:
                    print_error("No models found. Pull one using 'ollama pull <model>'")
                    return True, model_name
                    
                print_models_table(models_list, title="Select a Model")
                choice = IntPrompt.ask("[cyan]Enter the number of the model to use[/cyan]", choices=[str(i+1) for i in range(len(models_list))])
                args = get_model_name(models_list[choice - 1])
            except Exception as e:
                print_error(f"Error fetching models: {e}")
                return True, model_name
                
        new_model = args.strip()
        state.current_model_name = new_model
        console.print(
            Panel(
                f"[bold green]🔄 Switched active model to:[/bold green] [bold yellow]{new_model}[/bold yellow]",
                border_style="green",
                expand=False,
            )
        )
        return True, new_model

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
            html_content += f"<h1>Ollama Assistant Export ({state.current_session})</h1>"
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
        state.current_session = args.strip() or f"session_{int(time.time())}"
        messages.clear()
        messages.extend(load_history(state.current_session))
        console.print(f"[bold green]📂 Started new workspace:[/bold green] {state.current_session}")
        return True, model_name

    elif command == "/load":
        if args:
            state.current_session = args.strip()
            messages.clear()
            messages.extend(load_history(state.current_session))
            console.print(f"[bold green]📂 Loaded workspace:[/bold green] {state.current_session}")
        else:
            print_error("Specify a workspace name")
        return True, model_name

    elif command == "/chats":
        sessions = get_sessions()
        console.print("[bold cyan]Available Workspaces:[/bold cyan]")
        for s in sessions:
            mark = "★" if s == state.current_session else " "
            console.print(f"  [yellow]{mark}[/yellow] {s}")
        return True, model_name

    elif command == "/run":
        if not state.last_assistant_response:
            print_error("No response available to run.")
            return True, model_name

        blocks = re.findall(r"```(python|bash|sh)\n(.*?)```", state.last_assistant_response, re.DOTALL)
        if not blocks:
            print_error("No executable code blocks (python/bash) found in the last response.")
            return True, model_name

        lang, code = blocks[-1]
        console.print(Panel(code, title=f"[{lang}] Code to execute", border_style="yellow"))
        console.print("[bold red]WARNING: Executing generated code can be dangerous.[/bold red]")
        
        use_sandbox = Confirm.ask("[bold cyan]🛡️ Run in isolated Docker Sandbox (requires Docker)? [y/n][/bold cyan]", default=True)
        if not use_sandbox:
            if not Confirm.ask("[bold red]⚠️ Are you absolutely sure you want to execute this UNRESTRICTED on your machine?[/bold red]"):
                return True, model_name

        try:
            if use_sandbox:
                import docker
                client = docker.from_env()
                container_image = "python:3.11-slim" if lang == "python" else "ubuntu:latest"
                cmd_str = f"python -c \"{code}\"" if lang == "python" else f"bash -c \"{code}\""
                
                with console.status("[bold yellow]🐳 Running in Docker sandbox...[/bold yellow]"):
                    container = client.containers.run(container_image, cmd_str, remove=True, capture_output=True, text=True)
                    out = container
            else:
                if lang == "python":
                    import io, contextlib
                    out_buf = io.StringIO()
                    with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(out_buf):
                        exec(code, state.run_globals)
                    out = out_buf.getvalue()
                else:
                    result = subprocess.run(["bash", "-c", code], capture_output=True, text=True)
                    out = result.stdout + result.stderr

            console.print(Panel(out, title="[bold green]Output[/bold green]", border_style="green"))

            if Confirm.ask("Send output back to the assistant?"):
                handle_turn_cb(f"I ran the code. Here is the output:\n```\n{out}\n```", messages, model_name, config)
        except Exception as e:
            print_error(str(e))
        return True, model_name

        blocks = re.findall(r"```(python|bash|sh)\n(.*?)```", state.last_assistant_response, re.DOTALL)
        if not blocks:
            print_error("No executable code blocks (python/bash) found in the last response.")
            return True, model_name

        lang, code = blocks[-1]
        console.print(Panel(code, title=f"[{lang}] Code to execute", border_style="yellow"))
        console.print("[bold red]WARNING: Executing generated code can be dangerous. It has full access to your system.[/bold red]")
        if Confirm.ask("[bold red]⚠️ Are you absolutely sure you want to execute this code on your machine?[/bold red]"):
            try:
                if lang == "python":
                    import io
                    import contextlib

                    out_buf = io.StringIO()
                    with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(out_buf):
                        exec(code, state.run_globals)
                    out = out_buf.getvalue()
                else:
                    result = subprocess.run(["bash", "-c", code], capture_output=True, text=True)
                    out = result.stdout + result.stderr

                console.print(
                    Panel(out, title="[bold green]Output[/bold green]", border_style="green")
                )

                if Confirm.ask("Send output back to the assistant?"):
                    handle_turn_cb(
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
            handle_turn_cb(
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
                from langchain_community.document_loaders import DirectoryLoader, TextLoader
                from langchain.text_splitter import RecursiveCharacterTextSplitter
                from langchain_community.embeddings import OllamaEmbeddings
                from langchain_community.vectorstores import Chroma
                import warnings

                warnings.filterwarnings("ignore")
                db_path = str(Path.home() / ".config" / "ollama-assist" / "chroma_db")
                
                # Load documents
                loader = DirectoryLoader(directory, glob="**/*.*", loader_cls=TextLoader, silent_errors=True)
                docs = loader.load()
                
                # Split intelligently
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
                splits = text_splitter.split_documents(docs)
                
                # Embed and store
                embeddings = OllamaEmbeddings(model="nomic-embed-text") # Highly recommended local embedding model
                vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings, persist_directory=db_path)
                
                console.print(
                    Panel(
                        f"[bold green]✅ Ingested {len(docs)} files ({len(splits)} chunks) into the advanced Vector Database![/bold green]",
                        border_style="green",
                        expand=False,
                    )
                )
            except Exception as e:
                print_error(str(e))
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
                        except Exception as e:
                            print_error(f'Error reading {p}: {e}')
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
                from langchain_community.embeddings import OllamaEmbeddings
                from langchain_community.vectorstores import Chroma
                import warnings

                warnings.filterwarnings("ignore")
                db_path = str(Path.home() / ".config" / "ollama-assist" / "chroma_db")
                embeddings = OllamaEmbeddings(model="nomic-embed-text")
                vectorstore = Chroma(persist_directory=db_path, embedding_function=embeddings)
                
                results = vectorstore.similarity_search(query, k=3)
                
                context = ""
                for doc in results:
                    context += f"\n--- Source: {doc.metadata.get('source', 'Unknown')} ---\n{doc.page_content}\n"

                console.print(
                    Panel(context, title="[cyan]Retrieved Context[/cyan]", border_style="cyan")
                )

                prompt = f"Answer the user's question based ONLY on the following retrieved local documents:\n\n{context}\n\nQuestion: {query}"
                handle_turn_cb(prompt, messages, model_name, config, display_input=f"Ask RAG: {query}")
            except Exception as e:
                print_error(str(e))
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
                handle_turn_cb(prompt, messages, model_name, config, display_input=f"Ask RAG: {query}")
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
                    out = result.stdout + result.stderr
                else:
                    code_with_pwd = code + "\necho '---PWD_MARKER---'\npwd"
                    result = subprocess.run(["bash", "-c", code_with_pwd], capture_output=True, text=True)
                    raw_out = result.stdout + result.stderr
                    out = raw_out
                    
                    if "---PWD_MARKER---" in raw_out:
                        parts = raw_out.split("---PWD_MARKER---")
                        out = parts[0].strip()
                        new_dir = parts[1].strip()
                        import os
                        if new_dir and os.path.exists(new_dir):
                            os.chdir(new_dir)

                if not out.strip():
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
[bold cyan]Workspace Analytics ({state.current_session})[/bold cyan]
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
        handle_turn_cb(
            prompt, messages, model_name, config, display_input="<Pasted Clipboard Content>"
        )
        return True, model_name

    elif command in ["/lint", "/format"]:
        if not state.last_assistant_response:
            print_error("No response available.")
            return True, model_name

        blocks = re.findall(r"```python\n(.*?)```", state.last_assistant_response, re.DOTALL)
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
                        handle_turn_cb(
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
            handle_turn_cb(prompt, messages, model_name, config, display_input="Analyze system logs")
        except Exception as e:
            print_error(f"Could not read logs: {e}")
        return True, model_name


    elif command == "/speak":
        state.voice_enabled = not state.voice_enabled
        status = "ON" if state.voice_enabled else "OFF"
        console.print(Panel(f"[bold green]🔊 Text-to-Speech is now {status}[/bold green]", border_style="green", expand=False))
        return True, model_name

    elif command == "/persona":
        persona_name = args.strip()
        personas = config.get("personas", {})
        if not persona_name:
            console.print("[cyan]Available personas:[/cyan] " + ", ".join(personas.keys()))
            return True, model_name
            
        if persona_name in personas:
            sys_prompt = personas[persona_name]
            messages.append({"role": "system", "content": sys_prompt})
            console.print(Panel(f"[bold green]🎭 Switched persona to:[/bold green] {persona_name}", border_style="green", expand=False))
        else:
            print_error(f"Persona '{persona_name}' not found in config.")
        return True, model_name

    elif command == "/browse":
        url = args.strip()
        if not url.startswith("http"):
            url = "https://" + url
            
        with console.status(f"[bold yellow]🌐 Scraping {url}...[/bold yellow]"):
            try:
                import requests
                from bs4 import BeautifulSoup
                
                response = requests.get(url, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                text = ' '.join([p.text for p in soup.find_all('p')])
                
                preview = text[:500] + "..." if len(text) > 500 else text
                console.print(Panel(preview, title=f"[cyan]Scraped content from {url}[/cyan]"))
                
                prompt = f"I have scraped the following content from {url}:\n\n{text}\n\nPlease summarize or answer questions about this."
                handle_turn_cb(prompt, messages, model_name, config, display_input=f"Browse {url}")
            except Exception as e:
                print_error(f"Failed to scrape webpage: {e}")
        return True, model_name

    elif command == "/vision":
        parts = args.split(" ", 1)
        if len(parts) < 2:
            print_error("Usage: /vision <image_path> <prompt>")
            return True, model_name
            
        image_path, prompt = parts[0], parts[1]
        if not Path(image_path).exists():
            print_error("Image file not found.")
            return True, model_name
            
        with console.status("[bold yellow]👁️ Analyzing image...[/bold yellow]"):
            try:
                msg = {
                    'role': 'user',
                    'content': prompt,
                    'images': [image_path]
                }
                temp_messages = messages + [msg]
                handle_turn_cb(prompt, temp_messages, model_name, config, display_input=f"Vision: {prompt}")
                # We update the original messages with the assistant's reply (which handle_turn_cb does to temp_messages)
                if temp_messages[-1]['role'] == 'assistant':
                    messages.append(msg)
                    messages.append(temp_messages[-1])
            except Exception as e:
                print_error(f"Vision error: {e}")
        return True, model_name

    return False, model_name


