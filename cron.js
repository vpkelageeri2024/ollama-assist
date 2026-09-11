import { spawn } from 'child_process';
import path from 'path';
export function schedule_task(cron_expression, prompt) {
    // We will spawn a detached daemon that runs the cron job in the background.
    // The daemon will use terminal-wish headless or just directly hit ollama.
    // For simplicity, the daemon is just a node script.
    const daemonScript = `
import cron from 'node-cron';
import { Ollama } from 'ollama';
import fs from 'fs';
import os from 'os';

const ollama = new Ollama();
console.log("Daemon started with cron: ${cron_expression}");

cron.schedule('${cron_expression}', async () => {
    try {
        const response = await ollama.chat({
            model: 'qwen3:0.6b',
            messages: [{ role: 'user', content: '${prompt.replace(/'/g, "\\'")}' }]
        });
        const logMsg = \`[\\${new Date().toISOString()}] Task executed.\\nPrompt: ${prompt}\\nResult: \${response.message.content}\\n\\n\`;
        fs.appendFileSync(os.homedir() + '/.terminal-wish-cron.log', logMsg);
    } catch (e) {
        fs.appendFileSync(os.homedir() + '/.terminal-wish-cron.log', \`[\\${new Date().toISOString()}] Error: \${e}\\n\\n\`);
    }
});
`;
    const scriptPath = path.join(process.cwd(), 'daemon.mjs');
    require('fs').writeFileSync(scriptPath, daemonScript);
    // Spawn detached process
    const child = spawn(process.execPath, [scriptPath], {
        detached: true,
        stdio: 'ignore'
    });
    child.unref();
    return `Background task scheduled successfully. Cron: ${cron_expression}. Logs will be saved to ~/.terminal-wish-cron.log`;
}
