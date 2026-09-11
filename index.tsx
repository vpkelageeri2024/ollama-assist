import React, { useState, useEffect } from 'react';
import { render, Box, Text, useInput } from 'ink';
import TextInput from 'ink-text-input';
import Gradient from 'ink-gradient';
import BigText from 'ink-big-text';
import { Ollama } from 'ollama';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { execSync } from 'node:child_process';
import * as cheerio from 'cheerio';
import sqlite3 from 'sqlite3';
import { browser_goto, browser_click, browser_type, browser_read } from './browser.js';
import { initVoice, recordAudio, transcribeAudio, speakText } from './voice.js';
import { schedule_task } from './cron.js';
import { index_directory, semantic_search } from './vector.js';

const ollama = new Ollama({ host: 'http://127.0.0.1:11434' });

// --- Dynamic system discovery at startup ---
const HOME_DIR = os.homedir();
const USERNAME = os.userInfo().username;
const PLATFORM = os.platform();
const ARCH = os.arch();
const CWD = process.cwd();
const SHELL = process.env.SHELL || '/bin/bash';

// Scan the home directory to find what folders actually exist
function discoverHomeFolders(): string[] {
    try {
        const entries = fs.readdirSync(HOME_DIR, { withFileTypes: true });
        return entries
            .filter(e => e.isDirectory() && !e.name.startsWith('.'))
            .map(e => e.name);
    } catch {
        return [];
    }
}
const folderList = discoverHomeFolders().map(f => `  - ${f} -> ${path.join(HOME_DIR, f)}`).join('\n');


const DB_PATH = path.join(HOME_DIR, '.terminal-wish-memory.db');
const db = new sqlite3.Database(DB_PATH);
db.serialize(() => {
    db.run("CREATE TABLE IF NOT EXISTS memory (key TEXT PRIMARY KEY, value TEXT)");
});

function getMemory(): Promise<string> {
    return new Promise((resolve) => {
        db.all("SELECT key, value FROM memory", (err, rows: any[]) => {
            if (err || !rows || rows.length === 0) resolve("No memories saved.");
            else resolve(rows.map((r: any) => `- ${r.key}: ${r.value}`).join('\n'));
        });
    });
}

const SYSTEM_PROMPT = `You are Terminal Wish, an autonomous terminal AI assistant.

System info:
- User: ${USERNAME}
- Home: ${HOME_DIR}
- CWD: ${CWD}
- Existing folders in home:
${folderList}

RULES:
- NEVER guess paths. Linux is case-sensitive! (e.g. use "Documents" not "documents").
- ALWAYS check the "Existing folders" list above before using a path in a tool.
- If the user says "documents folder", check the list above for the exact casing and use that absolute path (e.g. ${HOME_DIR}/Documents/file.txt).
- Use run_command ("ls", "pwd") to explore if you are unsure.
- Always use absolute paths starting with /
- MEMORY: You have access to long-term memory. Use remember_fact to save important info (user name, preferences, context) and recall it in future sessions!
- VISION: If the user provides a path to an image (e.g. .png, .jpg), the image will be sent to you automatically. Look at it carefully!
- You have tools to search the web (search_web) and read webpages (read_webpage).
- ALWAYS use search_web if the user asks for real-time information, weather, news, or current events. Never say you don't have access to this information.`;

const tools = [
    {
        type: 'function',
        function: {
            name: 'index_directory',
            description: 'Read and mathematically index a directory for AI Semantic Search.',
            parameters: {
                type: 'object',
                properties: { dirPath: { type: 'string' } },
                required: ['dirPath']
            }
        }
    },
    {
        type: 'function',
        function: {
            name: 'semantic_search',
            description: 'Mathematically search the indexed codebase for a specific concept or code snippet.',
            parameters: {
                type: 'object',
                properties: { query: { type: 'string' } },
                required: ['query']
            }
        }
    },

    {
        type: 'function',
        function: {
            name: 'schedule_task',
            description: 'Schedule a background autonomous task using a cron expression.',
            parameters: {
                type: 'object',
                properties: {
                    cron_expression: { type: 'string', description: 'Standard cron expression e.g. * * * * *' },
                    prompt: { type: 'string', description: 'The prompt to run autonomously' }
                },
                required: ['cron_expression', 'prompt']
            }
        }
    },

    {
        type: 'function',
        function: {
            name: 'browser_goto',
            description: 'Navigate the headless browser to a specific URL.',
            parameters: { type: 'object', properties: { url: { type: 'string' } }, required: ['url'] }
        }
    },
    {
        type: 'function',
        function: {
            name: 'browser_click',
            description: 'Click a CSS selector in the browser.',
            parameters: { type: 'object', properties: { selector: { type: 'string' } }, required: ['selector'] }
        }
    },
    {
        type: 'function',
        function: {
            name: 'browser_type',
            description: 'Type text into a CSS selector in the browser.',
            parameters: { type: 'object', properties: { selector: { type: 'string' }, text: { type: 'string' } }, required: ['selector', 'text'] }
        }
    },
    {
        type: 'function',
        function: {
            name: 'browser_read',
            description: 'Extract all visible text from the current browser page.',
            parameters: { type: 'object', properties: {} }
        }
    },

    {
        type: 'function',
        function: {
            name: 'remember_fact',
            description: 'Save a fact about the user or system to long-term memory.',
            parameters: {
                type: 'object',
                properties: {
                    key: { type: 'string', description: 'Short unique identifier for this fact' },
                    value: { type: 'string', description: 'The fact to remember' }
                },
                required: ['key', 'value']
            }
        }
    },
    {
        type: 'function',
        function: {
            name: 'delete_fact',
            description: 'Delete a fact from long-term memory.',
            parameters: {
                type: 'object',
                properties: { key: { type: 'string' } },
                required: ['key']
            }
        }
    },
    {
        type: 'function',
        function: {
            name: 'replace_lines',
            description: 'Replace specific lines in a file. Lines are 1-indexed. Use this for surgical edits.',
            parameters: {
                type: 'object',
                properties: {
                    filepath: { type: 'string', description: 'Absolute path of the file' },
                    startLine: { type: 'number', description: 'Starting line number (1-indexed)' },
                    endLine: { type: 'number', description: 'Ending line number (inclusive)' },
                    newContent: { type: 'string', description: 'The new content to insert' }
                },
                required: ['filepath', 'startLine', 'endLine', 'newContent']
            }
        }
    },

    {
        type: 'function',
        function: {
            name: 'run_command',
            description: 'Execute a shell command on the system and return its stdout and stderr. Use this to explore the filesystem, install packages, run scripts, check system info, etc.',
            parameters: {
                type: 'object',
                properties: {
                    command: { type: 'string', description: 'The shell command to execute (e.g. "ls -la /home", "pwd", "cat file.txt", "mkdir -p /path/to/dir")' }
                },
                required: ['command']
            }
        }
    },
    {
        type: 'function',
        function: {
            name: 'create_file',
            description: 'Create a file with content at an absolute path. Parent directories are auto-created.',
            parameters: {
                type: 'object',
                properties: {
                    filepath: { type: 'string', description: 'Absolute path for the file' },
                    content: { type: 'string', description: 'Content to write' }
                },
                required: ['filepath', 'content']
            }
        }
    },
    {
        type: 'function',
        function: {
            name: 'read_file',
            description: 'Read the full contents of a file at an absolute path.',
            parameters: {
                type: 'object',
                properties: {
                    filepath: { type: 'string', description: 'Absolute path of the file to read' }
                },
                required: ['filepath']
            }
        }
    },
    {
        type: 'function',
        function: {
            name: 'search_web',
            description: 'Search the internet for a query using DuckDuckGo. Returns titles, snippets, and URLs.',
            parameters: {
                type: 'object',
                properties: {
                    query: { type: 'string', description: 'The search query' }
                },
                required: ['query']
            }
        }
    },
    {
        type: 'function',
        function: {
            name: 'read_webpage',
            description: 'Fetch and read the readable text content of a webpage URL. Use this to read documentation or search results.',
            parameters: {
                type: 'object',
                properties: {
                    url: { type: 'string', description: 'The absolute URL to fetch' }
                },
                required: ['url']
            }
        }
    }
];

async function executeTool(name: string, args: any): Promise<string> {
    try {
        if (name === 'run_command') {
            const output = execSync(args.command, {
                encoding: 'utf-8',
                timeout: 30000,
                maxBuffer: 1024 * 1024,
                cwd: HOME_DIR,
                shell: SHELL,
            });
            return output.trim() || '(command completed with no output)';
        } else if (name === 'create_file') {
            const dir = path.dirname(args.filepath);
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }
            fs.writeFileSync(args.filepath, args.content);
            return `File created: ${args.filepath}`;
        
        } else if (name === 'remember_fact') {
            return new Promise((resolve) => {
                db.run("INSERT OR REPLACE INTO memory (key, value) VALUES (?, ?)", [args.key, args.value], (err) => {
                    if (err) resolve(`Error saving memory: ${err.message}`);
                    else resolve(`Saved to memory: ${args.key}`);
                });
            });
        } else if (name === 'delete_fact') {
            return new Promise((resolve) => {
                db.run("DELETE FROM memory WHERE key = ?", [args.key], (err) => {
                    if (err) resolve(`Error deleting memory: ${err.message}`);
                    else resolve(`Deleted from memory: ${args.key}`);
                });
            });
        } else if (name === 'replace_lines') {
            const lines = fs.readFileSync(args.filepath, 'utf-8').split('\n');
            lines.splice(args.startLine - 1, args.endLine - args.startLine + 1, ...args.newContent.split('\n'));
            fs.writeFileSync(args.filepath, lines.join('\n'));
            return `Replaced lines ${args.startLine}-${args.endLine} in ${args.filepath}`;
} else if (name === 'read_file') {
            return fs.readFileSync(args.filepath, 'utf-8');
        
        
        
        } else if (name === 'index_directory') {
            return await index_directory(args.dirPath);
        } else if (name === 'semantic_search') {
            return await semantic_search(args.query);
} else if (name === 'schedule_task') {
            return schedule_task(args.cron_expression, args.prompt);
} else if (name === 'browser_goto') {
            return await browser_goto(args.url);
        } else if (name === 'browser_click') {
            return await browser_click(args.selector);
        } else if (name === 'browser_type') {
            return await browser_type(args.selector, args.text);
        } else if (name === 'browser_read') {
            return await browser_read();
} else if (name === 'search_web') {
            const response = await fetch("https://lite.duckduckgo.com/lite/", {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: "q=" + encodeURIComponent(args.query)
            });
            const html = await response.text();
            const $ = cheerio.load(html);
            const results: string[] = [];
            
            $(".result-snippet").each((i, el) => {
                const snippet = $(el).text().trim();
                const titleEl = $(el).closest('tr').prev().find('.result-link');
                const title = titleEl.text().trim();
                const url = titleEl.attr('href');
                if (title && snippet) {
                    results.push(`Title: ${title}\nURL: ${url}\nSnippet: ${snippet}`);
                }
            });
            return results.slice(0, 5).join('\n---\n') || 'No results found.';
        } else if (name === 'read_webpage') {
            const response = await fetch(args.url);
            const html = await response.text();
            const $ = cheerio.load(html);
            $('script, style, nav, footer, header, iframe, noscript').remove();
            const text = $('body').text().replace(/\s+/g, ' ').trim();
            return text.substring(0, 5000); // Limit to avoid blowing up context
        }
        return `Unknown tool: ${name}`;
    } catch (err: any) {
        // For run_command, capture stderr too
        if (err.stderr) {
            return `Error (exit ${err.status}):\nstdout: ${err.stdout || ''}\nstderr: ${err.stderr}`;
        }
        return `Error: ${err.message}`;
    }
}

const RenderContent = ({ msg }: { msg: any }) => {
    const lines: React.ReactElement[] = [];

    if (msg.thinking) {
        const thinkLines = msg.thinking.split('\n');
        lines.push(
            <Box key="think" paddingLeft={1} borderStyle="single" borderColor="gray" marginY={1} flexDirection="column">
                <Text color="gray" dimColor italic bold>🧠 Thinking:</Text>
                {thinkLines.map((line: string, idx: number) => (
                    <Text key={idx} color="gray" dimColor italic>  {line}</Text>
                ))}
            </Box>
        );
    }

    if (msg.content) {
        lines.push(<Text key="content">{msg.content}</Text>);
    }

    return <Box flexDirection="column">{lines}</Box>;
};

// --- Animated Spinner ---
const SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

const Spinner = ({ color = 'yellow' }: { color?: string }) => {
    const [frame, setFrame] = useState(0);
    useEffect(() => {
        const timer = setInterval(() => {
            setFrame(prev => (prev + 1) % SPINNER_FRAMES.length);
        }, 80);
        return () => clearInterval(timer);
    }, []);
    return <Text color={color}>{SPINNER_FRAMES[frame]}</Text>;
};

// --- Status Bar with animation ---
const StatusBar = ({ statusText, phase }: { statusText: string; phase: string }) => {
    const phaseColors: Record<string, string> = {
        thinking: 'cyan',
        running: 'yellow',
        processing: 'magenta',
        waiting_approval: 'red',
    };
    const color = phaseColors[phase] || 'yellow';

    return (
        <Box borderStyle="round" borderColor={color} paddingX={1} marginTop={1} flexDirection="column">
            <Box>
                <Spinner color={color} />
                <Text color={color} bold> {statusText}</Text>
            </Box>
        </Box>
    );
};

const App = () => {
    const [input, setInput] = useState('');
    const [messages, setMessages] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [statusText, setStatusText] = useState('');
    const [phase, setPhase] = useState('thinking');
    const [isRecording, setIsRecording] = useState(false);
    const [pendingAction, setPendingAction] = useState<{toolName: string, args: any, resolve: (approved: boolean) => void} | null>(null);

    
    useInput((input, key) => {
        
        if (input.toLowerCase() === 'v' && !pendingAction && !isLoading && !isRecording) {
            (async () => {
                setIsRecording(true);
                const tmpPath = path.join(os.tmpdir(), 'wish_voice.wav');
                await recordAudio(tmpPath, 5000);
                setStatusText('Transcribing voice...');
                setPhase('processing');
                setIsRecording(false);
                const transcript = await transcribeAudio(tmpPath);
                handleSubmit(transcript);
            })();
            return;
        }
        
        if (pendingAction) {
            if (input.toLowerCase() === 'y') {
                pendingAction.resolve(true);
                setPendingAction(null);
            } else if (input.toLowerCase() === 'n') {
                pendingAction.resolve(false);
                setPendingAction(null);
            }
        }
    });

    const handleSubmit = async (query: string) => {
        if (!query.trim()) return;

        
        let activeModel = 'qwen3:0.6b';
        let images: Uint8Array[] = [];
        
        // Vision: detect image paths in query
        const imageMatches = query.match(/(?:\/|~)[^\s]+?\.(?:png|jpg|jpeg)/gi);
        if (imageMatches) {
            for (const p of imageMatches) {
                const fullPath = p.replace('~', HOME_DIR);
                if (fs.existsSync(fullPath)) {
                    images.push(fs.readFileSync(fullPath));
                }
            }
            if (images.length > 0) {
                activeModel = 'llava'; // Switch to vision model!
            }
        }

        // Memory injection
        const memories = await getMemory();
        const dynamicSystemPrompt = SYSTEM_PROMPT + "\n\nSAVED MEMORIES:\n" + memories;

        let currentMessages: any[] = [
            { role: 'system', content: dynamicSystemPrompt },
            ...messages,
            { role: 'user', content: query, images: images.length > 0 ? images : undefined }
        ];

        setMessages(prev => [...prev, { role: 'user', content: query }]);
        setInput('');
        setIsLoading(true);
        setPhase('thinking');
        setStatusText('Sending to model...');

        try {
            let response = await ollama.chat({
                model: activeModel,
                messages: currentMessages,
                stream: false,
                tools: tools as any
            });

            // Tool calling loop - keep going until the model stops calling tools
            let maxIterations = 10; // Safety limit
            while (response.message.tool_calls && response.message.tool_calls.length > 0 && maxIterations > 0) {
                maxIterations--;

                // Show tool call in UI
                setMessages(prev => [...prev, { ...response.message }]);
                currentMessages = [...currentMessages, response.message];

                for (const tool of response.message.tool_calls) {
                    const toolName = tool.function.name;
                    const toolArgs = tool.function.arguments;
                    
                    setPhase('running');
                    if (toolName === 'run_command') {
                        setStatusText(`$ ${toolArgs.command}`);
                    } else if (toolName === 'create_file') {
                        setStatusText(`Writing → ${toolArgs.filepath}`);
                    } else if (toolName === 'read_file') {
                        setStatusText(`Reading → ${toolArgs.filepath}`);
                    } else {
                        setStatusText(`${toolName}...`);
                    }
                    
                    
                    let isSafe = true;
                    if (toolName === 'run_command') {
                        const safeCommands = ['ls', 'pwd', 'cat', 'echo', 'which', 'git status', 'whoami'];
                        const cmd = toolArgs.command.trim();
                        isSafe = safeCommands.some(safe => cmd.startsWith(safe));
                    } else if (toolName === 'create_file' || toolName === 'replace_lines') {
                        isSafe = false;
                    }

                    let result = '';
                    if (!isSafe) {
                        setPhase('waiting_approval');
                        setStatusText(`Allow ${toolName}? (y/n)`);
                        
                        const approved = await new Promise<boolean>((resolve) => {
                            setPendingAction({ toolName, args: toolArgs, resolve });
                        });
                        
                        if (!approved) {
                            result = "User denied permission to run this tool.";
                        } else {
                            setPhase('running');
                            result = await executeTool(toolName, toolArgs);
                        }
                    } else {
                        setPhase('running');
                        result = await executeTool(toolName, toolArgs);
                    }

                    currentMessages.push({ role: 'tool', content: result });
                }

                setPhase('processing');
                setStatusText('Analyzing results...');
                response = await ollama.chat({
                    model: activeModel,
                    messages: currentMessages,
                    stream: false,
                    tools: tools as any
                });
            }

            setMessages(prev => [...prev, response.message]);
            if (response.message.content) { speakText(response.message.content); }

        } catch (e: any) {
            setMessages(prev => [...prev, { role: 'system', content: `Error: ${e.message}` }]);
        }
        setIsLoading(false);
    };

    return (
        <Box flexDirection="column" padding={1} width="100%">
            <Box justifyContent="center" marginBottom={1}>
                <Gradient name="mind">
                    <BigText text="TERMINAL WISH" font="chrome" />
                </Gradient>
            </Box>

            <Box flexDirection="column" borderStyle="round" borderColor="cyan" padding={1} minHeight={15}>
                {messages.length === 0 && (
                    <Box justifyContent="center" height={10} alignItems="center">
                        <Text color="gray" italic>Type your first message to begin...</Text>
                    </Box>
                )}
                {messages.map((msg, i) => {
                    if (msg.role === 'tool' || msg.role === 'system') return null;
                    return (
                        <Box key={i} marginBottom={1} flexDirection="column">
                            <Box>
                                {msg.role === 'user' ? (
                                    <Text backgroundColor="green" color="black" bold> YOU </Text>
                                ) : (
                                    <Text backgroundColor="cyan" color="black" bold> ASSISTANT </Text>
                                )}
                            </Box>
                            
                            <Box paddingLeft={1} marginTop={1}>
                                {msg.role === 'assistant' ? <RenderContent msg={msg} /> : <Text>{msg.content}</Text>}
                            </Box>

                            {msg.tool_calls && msg.tool_calls.length > 0 && (
                                <Box paddingLeft={1} marginTop={1} flexDirection="column">
                                    <Text backgroundColor="magenta" color="black" bold> ACTION </Text>
                                    {msg.tool_calls.map((tc: any, j: number) => (
                                        <Box key={j} paddingLeft={1} marginTop={1}>
                                            <Text color="yellow" italic>
                                                {tc.function.name === 'run_command' 
                                                    ? `⚡ $ ${tc.function.arguments.command}`
                                                    : `🛠️ ${tc.function.name}(${JSON.stringify(tc.function.arguments)})`
                                                }
                                            </Text>
                                        </Box>
                                    ))}
                                </Box>
                            )}
                        </Box>
                    );
                })}
            </Box>

            {isRecording ? (
                <Box borderStyle="round" borderColor="red" paddingX={1} marginTop={1}>
                    <Spinner color="red" />
                    <Text color="red" bold> 🎙️ Recording... Speak now! (5s)</Text>
                </Box>
            ) : pendingAction ? (
                <Box borderStyle="round" borderColor="red" paddingX={1} marginTop={1}>
                    <Text color="red" bold>⚠️ Allow {pendingAction.toolName} to run? (y/n) </Text>
                </Box>
            ) : isLoading ? (
                <StatusBar statusText={statusText} phase={phase} />
            ) : (
                <Box borderStyle="round" borderColor="green" paddingX={1} marginTop={1}>
                    <Text color="green">❯ </Text>
                    <TextInput value={input} onChange={setInput} onSubmit={handleSubmit} />
                </Box>
            )}
        </Box>
    );
};

render(<App />);
