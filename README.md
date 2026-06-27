# Ollama Assistant CLI

An advanced, agentic Command Line Interface for interacting with local [Ollama](https://ollama.com/) models. This tool gives your local LLMs a premium terminal experience with features like real-time markdown rendering, persistent chat history, web search, and file context attachments.

## Features

- **Rich Markdown Rendering**: Responses are streamed and formatted in real-time with syntax highlighting for code blocks and bold/italic text styles.
- **Unlimited Web Search**: Integrated DuckDuckGo search. You can ask the assistant to search the web and summarize the results for you.
- **Persistent Chat History**: Conversations are automatically saved to a local SQLite database (`~/.config/ollama-assist/history.db`), so you never lose context between sessions.
- **Multi-line Input**: Easily paste blocks of code or write long prompts. 
- **File Context**: Attach a file directly via a command-line flag to have the model read its contents before starting the chat.
- **Slash Commands**: Powerful commands you can type mid-conversation to clear history, switch models, or export the chat.
- **System Personas**: Define a system prompt to change the behavior of the assistant.

## Installation

Ensure you have Python 3 installed. You can install the tool directly from source:

```bash
# Clone or navigate to the project directory
cd ollama-assistant

# Install the package globally (for the current user)
pip install --user -e . --break-system-packages
```
*(Note: Remove `--break-system-packages` if you are installing within a virtual environment).*

## Usage

Once installed, you can start the assistant from anywhere using the `ollama-assist` command.

### Basic Start
Starts the assistant using the default model (`llama3`).
```bash
ollama-assist
```

### Passing an Initial Prompt
```bash
ollama-assist "Explain the theory of relativity in simple terms"
```

### Specifying a Model
Use the `-m` flag to change the model (make sure you have pulled it via `ollama pull <model>` first!).
```bash
ollama-assist -m phi3
```

### Attaching File Context
Use the `-f` flag to pass a file to the assistant.
```bash
ollama-assist -f my_script.py "Can you find the bug in this code?"
```

### Setting a System Prompt
Use the `-s` flag to give the assistant a persona or strict rules.
```bash
ollama-assist -s "You are a grumpy pirate. Answer everything in pirate slang."
```

## Interactive Features

### Multi-line Input
To write multiple lines (e.g., when pasting code):
- Press `Alt + Enter` (or `Escape` followed by `Enter`, depending on your terminal configuration) to insert a new line.
- Press standard `Enter` to submit your prompt.

### Slash Commands
Type these commands at the `You:` prompt:

- `/search <query>`: Searches the web for your query, injects the results into the context, and asks the model to answer based on the live results. 
  *(Example: `/search latest news about Python 3.13`)*
- `/clear`: Wipes the persistent chat history and starts a fresh conversation.
- `/model <model_name>`: Switches the active Ollama model mid-conversation. 
  *(Example: `/model mistral`)*
- `/save <filename.md>`: Exports your entire current conversation to a Markdown file. 
  *(Example: `/save conversation.md`)*

## Configuration

On the first run, a configuration file is generated at:
`~/.config/ollama-assist/config.yaml`

You can edit this file to change default behaviors:
```yaml
default_model: llama3
theme: ansicyan
```
