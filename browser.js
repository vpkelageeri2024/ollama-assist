import puppeteer from 'puppeteer';
let browser = null;
let page = null;
export async function browser_goto(url) {
    if (!browser) {
        browser = await puppeteer.launch({ headless: true });
        page = await browser.newPage();
    }
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    return `Navigated to ${url}. Title: ${await page.title()}`;
}
export async function browser_click(selector) {
    if (!page)
        return "Error: No active browser session.";
    await page.click(selector);
    return `Clicked ${selector}`;
}
export async function browser_type(selector, text) {
    if (!page)
        return "Error: No active browser session.";
    await page.type(selector, text);
    return `Typed into ${selector}`;
}
export async function browser_read() {
    if (!page)
        return "Error: No active browser session.";
    const text = await page.evaluate(() => document.body.innerText);
    return text.substring(0, 4000);
}
