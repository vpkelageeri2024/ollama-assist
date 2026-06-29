import re
from pathlib import Path

cli_path = Path("ollama_assistant/cli.py")
commands_path = Path("ollama_assistant/commands.py")
config_path = Path("ollama_assistant/config.py")
state_path = Path("ollama_assistant/state.py")

cli_content = cli_path.read_text()
commands_content = commands_path.read_text()
config_content = config_path.read_text()
state_content = state_path.read_text()

# --- 1. STATE ---
state_content = state_content.replace(
    'run_globals: Dict[str, Any] = field(default_factory=dict)',
    'run_globals: Dict[str, Any] = field(default_factory=dict)\n    raw_mode: bool = False\n    voice_enabled: bool = False'
)
state_path.write_text(state_content)

# --- 2. CONFIG & WIZARD ---
new_config = """import os
import yaml
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm

CONFIG_DIR = Path.home() / ".config" / "ollama-assist"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG = {
    "theme": "ansicyan",
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
    console.print("Let's configure your terminal AI experience.\\n")
    
    user_name = Prompt.ask("[cyan]What should I call you?[/cyan]", default="You")
    theme = Prompt.ask("[cyan]Choose a UI theme color (e.g., ansicyan, green, magenta, red)[/cyan]", default="ansicyan")
    
    config = DEFAULT_CONFIG.copy()
    config["user_name"] = user_name
    config["theme"] = theme
    
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f)
        
    console.print("[bold green]✅ Configuration saved! Starting assistant...[/bold green]\\n")
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
"""
config_path.write_text(new_config)


# --- 3. COMMANDS ---
new_commands = """
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
                
                prompt = f"I have scraped the following content from {url}:\\n\\n{text}\\n\\nPlease summarize or answer questions about this."
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
"""
commands_content = commands_content.replace('    return False, model_name', new_commands + '\n    return False, model_name')
commands_path.write_text(commands_content)


# --- 4. CLI ---
# Add --raw and --voice args
cli_content = cli_content.replace(
    'parser.add_argument("prompt", type=str, nargs="*", help="Initial prompt")',
    'parser.add_argument("prompt", type=str, nargs="*", help="Initial prompt")\n    parser.add_argument("--raw", action="store_true", help="Output raw text/JSON without UI")\n    parser.add_argument("--voice", action="store_true", help="Enable text-to-speech")'
)

# Apply args to state
cli_content = cli_content.replace(
    'state.current_session = args.workspace\n    initial_prompt = " ".join(args.prompt) if args.prompt else None',
    'state.current_session = args.workspace\n    state.raw_mode = args.raw\n    state.voice_enabled = args.voice\n    initial_prompt = " ".join(args.prompt) if args.prompt else None'
)

# Skip welcome banner if raw mode
cli_content = cli_content.replace(
    'print_welcome_banner(model_name)\n    check_for_updates()',
    'if not state.raw_mode:\n        print_welcome_banner(model_name)\n        check_for_updates()'
)

# Modify handle_turn to support raw mode and TTS
old_handle_turn_start = "def handle_turn(user_input: str, messages: list, model_name: str, config: dict, display_input: str = None):"
new_handle_turn = """def handle_turn(user_input: str, messages: list, model_name: str, config: dict, display_input: str = None):
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
            sys.stdout.write("\\n")
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
"""

# We need to replace the entire handle_turn function. Since it's at the end of the file, we can do:
idx = cli_content.find("def handle_turn(user_input")
cli_content = cli_content[:idx] + new_handle_turn

# In raw mode, exit if initial_prompt is given (since it acts as a pipe)
cli_content = cli_content.replace(
    'if initial_prompt:\n        timestamp = datetime.now().strftime("%H:%M")\n        console.print(\n            f"[{theme_color} bold]{user_name}:[/] {initial_prompt} [dim]({timestamp})[/dim]"\n        )\n        handle_turn(initial_prompt, messages, state.current_model_name, config)\n\n    while True:',
    'if initial_prompt:\n        if not state.raw_mode:\n            timestamp = datetime.now().strftime("%H:%M")\n            console.print(f"[{theme_color} bold]{user_name}:[/] {initial_prompt} [dim]({timestamp})[/dim]")\n        handle_turn(initial_prompt, messages, state.current_model_name, config)\n        if state.raw_mode:\n            sys.exit(0)\n\n    if state.raw_mode:\n        sys.exit(0)\n\n    while True:'
)

cli_path.write_text(cli_content)

print("V3 Features implemented successfully.")
