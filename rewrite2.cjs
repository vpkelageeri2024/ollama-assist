const fs = require('fs');

let code = fs.readFileSync('index.tsx', 'utf-8');

// 1. Add imports
code = code.replace(
    "import sqlite3 from 'sqlite3';",
    "import sqlite3 from 'sqlite3';\nimport { browser_goto, browser_click, browser_type, browser_read } from './browser.js';\nimport { initVoice, recordAudio, transcribeAudio, speakText } from './voice.js';"
);

// 2. Add tools
const newTools = `
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
`;
code = code.replace("const tools = [", "const tools = [" + newTools);

// 3. Add to executeTool
const browserExecution = `
        } else if (name === 'browser_goto') {
            return await browser_goto(args.url);
        } else if (name === 'browser_click') {
            return await browser_click(args.selector);
        } else if (name === 'browser_type') {
            return await browser_type(args.selector, args.text);
        } else if (name === 'browser_read') {
            return await browser_read();
`;
code = code.replace("} else if (name === 'search_web') {", browserExecution + "} else if (name === 'search_web') {");

// 4. Update the App component for Voice Mode
code = code.replace(
    "const [phase, setPhase] = useState('thinking');",
    "const [phase, setPhase] = useState('thinking');\n    const [isRecording, setIsRecording] = useState(false);"
);

const inputHandler = `
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
        
        if (pendingAction) {`;
code = code.replace("if (pendingAction) {", inputHandler);

code = code.replace(
    "setMessages(prev => [...prev, response.message]);",
    "setMessages(prev => [...prev, response.message]);\n            if (response.message.content) { speakText(response.message.content); }"
);

code = code.replace(
    "{pendingAction ? (",
    `{isRecording ? (
                <Box borderStyle="round" borderColor="red" paddingX={1} marginTop={1}>
                    <Spinner color="red" />
                    <Text color="red" bold> 🎙️ Recording... Speak now! (5s)</Text>
                </Box>
            ) : pendingAction ? (`
);

fs.writeFileSync('index.tsx', code);
