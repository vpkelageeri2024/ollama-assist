const fs = require('fs');

let code = fs.readFileSync('index.tsx', 'utf-8');

// 1. Add cron import
code = code.replace(
    "import { initVoice, recordAudio, transcribeAudio, speakText } from './voice.js';",
    "import { initVoice, recordAudio, transcribeAudio, speakText } from './voice.js';\nimport { schedule_task } from './cron.js';"
);

// 2. Add cron tool
const cronTool = `
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
`;
code = code.replace("const tools = [", "const tools = [" + cronTool);

// 3. Add to executeTool
const cronExecution = `
        } else if (name === 'schedule_task') {
            return schedule_task(args.cron_expression, args.prompt);
`;
code = code.replace("} else if (name === 'browser_goto') {", cronExecution + "} else if (name === 'browser_goto') {");

fs.writeFileSync('index.tsx', code);
