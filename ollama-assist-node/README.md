# 🧞 Terminal Wish

A beautiful, fully-autonomous AI assistant that lives directly in your terminal. Powered by Ollama, it can browse the web, surgically edit files, execute terminal commands with safety guardrails, see images, and remember facts about you!

## ✨ Features
- **Autonomy:** It doesn't just chat; it uses tools to run commands, read files, and write code.
- **Safety Guardrails:** Safe commands (like `ls` or `pwd`) run instantly. Dangerous commands pause and wait for your `(y/n)` approval.
- **Long-Term Memory:** Uses a local SQLite database to remember facts across sessions (e.g., "Remember my favorite language is Python").
- **Web Browsing:** Can search the internet for real-time information.
- **Vision:** Pass it a screenshot, and it will look at it and describe it.
- **Surgical Code Editing:** Can edit precise line numbers in large files without rewriting the whole document.

---

## 🛠️ Prerequisites

Before you can use Terminal Wish, you need to have two things installed on your computer:

1. **Node.js** (v20 or higher)
   - Download from [nodejs.org](https://nodejs.org/) or install via your package manager.
2. **Ollama** (Local AI runtime)
   - Download from [ollama.com](https://ollama.com/) or install via terminal:
     `curl -fsSL https://ollama.com/install.sh | sh`

---

## 🚀 Installation

### 1. Download the AI Models
Terminal Wish uses small, hyper-fast local models. Run these commands in your terminal to download them:

```bash
# The main assistant model (very fast, requires ~1GB RAM)
ollama run qwen3:0.6b

# (Optional) The vision model to look at images (requires ~4GB RAM)
ollama run llava
```
*(You can hit `Ctrl+C` to exit the Ollama chat once they finish downloading).*

### 2. Install Terminal Wish
Install the CLI tool globally using NPM:

```bash
npm install -g terminal-wish
```

---

## 🎮 Usage

Simply open your terminal and type:
```bash
terminal-wish
```

### Try these prompts:
- *"What is the weather in Tokyo right now?"* (Tests Web Browsing)
- *"Remember that my name is Vishal."* (Tests Memory)
- *"Create a python script that prints hello world."* (Tests File Creation)
- *"What is going on in this image: ~/Downloads/screenshot.png"* (Tests Vision)
