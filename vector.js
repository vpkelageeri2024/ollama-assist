import { pipeline } from '@xenova/transformers';
import sqlite3 from 'sqlite3';
import fs from 'fs';
import path from 'path';
import os from 'os';
const DB_PATH = path.join(os.homedir(), '.terminal-wish-memory.db');
const db = new sqlite3.Database(DB_PATH);
db.serialize(() => {
    db.run("CREATE TABLE IF NOT EXISTS vector_index (id INTEGER PRIMARY KEY, filepath TEXT, content TEXT, vector TEXT)");
});
let extractor = null;
async function getExtractor() {
    if (!extractor) {
        extractor = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2');
    }
    return extractor;
}
function cosineSimilarity(vecA, vecB) {
    let dotProduct = 0;
    let normA = 0;
    let normB = 0;
    for (let i = 0; i < vecA.length; i++) {
        dotProduct += vecA[i] * vecB[i];
        normA += vecA[i] * vecA[i];
        normB += vecB[i] * vecB[i];
    }
    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}
export async function index_directory(dirPath) {
    const ext = await getExtractor();
    let files = [];
    function walk(dir) {
        if (files.length > 50)
            return; // Limit for performance
        try {
            const list = fs.readdirSync(dir);
            for (let file of list) {
                if (file.startsWith('.') || file === 'node_modules' || file === 'dist')
                    continue;
                const fp = path.join(dir, file);
                const stat = fs.statSync(fp);
                if (stat.isDirectory())
                    walk(fp);
                else if (stat.isFile() && stat.size < 100000)
                    files.push(fp);
            }
        }
        catch (e) { }
    }
    walk(dirPath);
    let count = 0;
    for (const file of files) {
        try {
            const content = fs.readFileSync(file, 'utf-8').substring(0, 1000);
            const output = await ext(content, { pooling: 'mean', normalize: true });
            const vectorArray = Array.from(output.data);
            await new Promise((resolve) => {
                db.run("INSERT INTO vector_index (filepath, content, vector) VALUES (?, ?, ?)", [file, content, JSON.stringify(vectorArray)], resolve);
            });
            count++;
        }
        catch (e) { }
    }
    return `Indexed ${count} files in ${dirPath}.`;
}
export async function semantic_search(query) {
    const ext = await getExtractor();
    const output = await ext(query, { pooling: 'mean', normalize: true });
    const queryVector = Array.from(output.data);
    return new Promise((resolve) => {
        db.all("SELECT filepath, content, vector FROM vector_index", (err, rows) => {
            if (err || !rows || rows.length === 0) {
                resolve("Search failed or index is empty. Please run index_directory first.");
                return;
            }
            for (let row of rows) {
                try {
                    const docVec = JSON.parse(row.vector);
                    row.score = cosineSimilarity(queryVector, docVec);
                }
                catch (e) {
                    row.score = 0;
                }
            }
            rows.sort((a, b) => b.score - a.score);
            const top = rows.slice(0, 3);
            let res = `Top 3 matches for "${query}":\n`;
            for (let t of top) {
                res += `\n--- File: ${t.filepath} (Score: ${t.score.toFixed(2)}) ---\n${t.content.substring(0, 300)}...\n`;
            }
            resolve(res);
        });
    });
}
