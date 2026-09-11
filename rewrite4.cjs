const fs = require('fs');

let code = fs.readFileSync('index.tsx', 'utf-8');

// 1. Add vector import
code = code.replace(
    "import { schedule_task } from './cron.js';",
    "import { schedule_task } from './cron.js';\nimport { index_directory, semantic_search } from './vector.js';"
);

// 2. Add vector tools
const vectorTools = `
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
`;
code = code.replace("const tools = [", "const tools = [" + vectorTools);

// 3. Add to executeTool
const vectorExecution = `
        } else if (name === 'index_directory') {
            return await index_directory(args.dirPath);
        } else if (name === 'semantic_search') {
            return await semantic_search(args.query);
`;
code = code.replace("} else if (name === 'schedule_task') {", vectorExecution + "} else if (name === 'schedule_task') {");

fs.writeFileSync('index.tsx', code);
