import { pipeline } from '@xenova/transformers';
import { spawn, exec } from 'child_process';
let transcriber = null;
export async function initVoice() {
    if (!transcriber) {
        transcriber = await pipeline('automatic-speech-recognition', 'Xenova/whisper-tiny.en');
    }
}
export function recordAudio(filePath, durationMs = 5000) {
    return new Promise((resolve) => {
        // use rec (sox) to record 16kHz mono audio
        const rec = spawn('rec', ['-q', '-c', '1', '-r', '16000', filePath]);
        setTimeout(() => {
            rec.kill();
            resolve();
        }, durationMs);
    });
}
export async function transcribeAudio(filePath) {
    if (!transcriber)
        await initVoice();
    const result = await transcriber(filePath);
    return result.text;
}
export function speakText(text) {
    // Strip quotes and special chars that might break espeak
    const cleanText = text.replace(/["'$`\\]/g, ' ').substring(0, 500);
    exec(`espeak -s 150 "${cleanText}"`);
}
