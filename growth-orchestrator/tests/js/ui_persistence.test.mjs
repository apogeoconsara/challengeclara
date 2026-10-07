// Switching tabs or reloading must not lose what a person did on the page. Needs a browser: skipped when playwright-core
// (or Chromium) is not available. Run from the repo root: node growth-orchestrator/tests/js/ui_persistence.test.mjs
import http from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { extname, join } from "node:path";
import assert from "node:assert/strict";

let chromium;
try { ({ chromium } = await import("playwright-core")); } catch { console.log("skipped: playwright-core not installed"); process.exit(0); }
const exe = process.env.CHROMIUM_PATH || ["/opt/pw-browsers/chromium", "/usr/bin/chromium", "/usr/bin/chromium-browser"].find(existsSync);
if (!exe) { console.log("skipped: no Chromium found"); process.exit(0); }

const types = { ".html": "text/html", ".json": "application/json", ".js": "text/javascript" };
const server = http.createServer((req, res) => {
  const f = join("public", req.url.split("?")[0] === "/" ? "index.html" : req.url.split("?")[0]);
  if (!existsSync(f)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { "content-type": types[extname(f)] || "text/plain" }); res.end(readFileSync(f));
}).listen(0);
const base = `http://localhost:${server.address().port}/`;

const browser = await chromium.launch({ executablePath: exe, args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = []; page.on("pageerror", e => errors.push(e.message));
const go = async v => { await page.click(`#nav button[data-v="${v}"]`); await page.waitForTimeout(250); };
const goSec = async (group, sec) => { await go(group); await page.click(`[data-sec="${sec}"]`); await page.waitForTimeout(250); };
const text = sel => page.$eval(sel, e => e.innerText);

await page.goto(base + "#run"); await page.waitForSelector("#runGo");

// 1. a finished flow is still there after visiting another tab
await page.click("#runGo"); await page.click("#runSkip");
assert.match(await text("#runCard"), /Result:/);
await go("overview"); await go("run");
assert.match(await text("#runCard"), /Result:/, "finished flow lost after switching tabs");

// 2. a run that is still animating keeps going while another tab is open
await page.click('[data-run="F3"]'); await page.click("#runGo");
await go("operations"); await page.waitForTimeout(11500); await go("run");
assert.match(await text("#runCard"), /Result:/, "a run in progress stopped when the tab changed");

// 3. the model-vs-rules replay survives tab changes and a reload
await page.click("#truthRun"); await page.waitForTimeout(4200);
await goSec("decisions", "priority"); await go("run");
assert.match(await text("#trio"), /SUPPRESS/, "replay lost after switching tabs");
await page.reload(); await page.waitForSelector("#trio");
assert.match(await text("#trio"), /SUPPRESS/, "replay lost after a reload");

// 4. Architecture keeps the open scenario list
await go("flows"); await page.click("#moreCases > summary"); await page.click("tr.click");
await go("overview"); await go("flows");
assert.ok(await page.$eval("#detail", e => e.innerText.length > 50), "the opened scenario was closed by switching tabs");

// 5. weights, account choice and typed reply survive a reload
await goSec("decisions", "priority"); await page.fill("#w_size", "41"); await page.reload(); await page.waitForSelector("#w_size");
assert.equal(await page.inputValue("#w_size"), "41", "edited weight lost on reload");
await goSec("decisions", "account"); const id = await page.$eval("#audSel option:nth-child(7)", o => o.value); await page.selectOption("#audSel", id);
await go("overview"); await goSec("decisions", "account");
assert.equal(await page.inputValue("#audSel"), id, "chosen account lost after switching tabs");
await goSec("aisafety", "live"); await page.fill("#reply", "Please call me next week"); await go("overview"); await go("aisafety");
assert.equal(await page.inputValue("#reply"), "Please call me next week", "typed reply lost after switching tabs");

// 6. a trace section you opened stays open
await go("flows");
if (!(await page.$eval("#moreCases", d => d.open))) await page.click("#moreCases > summary");   // "More cases" (it is already open: that is the point)
await page.click("tr.click");                                           // open a scenario
await page.waitForSelector("#detail details summary");
const audit = (await page.$$("#detail details")).find(Boolean);
const summaryText = await audit.$eval("summary", e => e.textContent);
await audit.$eval("summary", e => e.click());
const openBefore = await audit.evaluate(d => d.open);
await go("overview"); await go("flows");
const again = (await page.$$("#detail details"))[0];
assert.equal(await again.evaluate(d => d.open), openBefore, `"${summaryText}" changed state after switching tabs`);

// 6b. approval decisions survive tab changes and a reload, and are reflected on the Command Center
await go("approvals"); await page.waitForSelector("#apApprove");
await page.click("#apApprove"); await page.selectOption("#apReason", "Tone or wording"); await page.click("#apReject");
await go("overview"); assert.match(await text("#main"), /Approval queue: 1 approved, 1 rejected/);
await page.reload(); await go("approvals"); assert.match(await text("#apKpi"), /1 \/ 1 \/ 198/, "approval decisions lost");

// 6c. a group reopens on the section you were in
await goSec("aisafety", "evals"); await go("overview"); await go("aisafety");
assert.ok(await page.$eval('[data-sec="evals"]', b => b.classList.contains("active")), "the group did not reopen on its last section");

// 7. Reset demo clears what you changed
await goSec("decisions", "priority"); await page.fill("#w_size", "44");
page.once("dialog", d => d.accept()); await page.click("#resetDemo"); await page.waitForSelector("#main h1");
await goSec("decisions", "priority");
assert.equal(await page.inputValue("#w_size"), "30", "Reset demo did not restore the default weight");
await go("approvals"); await page.waitForSelector("#apApprove"); assert.match(await text("#apKpi"), /0 \/ 0 \/ 200/, "Reset demo did not clear the approvals");

// 8. with storage blocked the page still keeps your changes while the tab is open, and says so
const blocked = await browser.newPage({ viewport: { width: 1280, height: 900 } });
await blocked.addInitScript(() => { Object.defineProperty(window, "localStorage", { get() { throw new Error("blocked"); } }); });
const berrors = []; blocked.on("pageerror", e => berrors.push(e.message));
await blocked.goto(base + "#priority"); await blocked.waitForSelector("#w_size");
assert.match(await blocked.$eval("#main", e => e.innerText), /blocking site storage/);
await blocked.fill("#w_size", "37");
await blocked.click('#nav button[data-v="overview"]'); await blocked.waitForTimeout(250); await blocked.click('#nav button[data-v="decisions"]'); await blocked.waitForSelector("#w_size");
assert.equal(await blocked.inputValue("#w_size"), "37", "with storage blocked, an edit was lost on a tab change");
assert.deepEqual(berrors, []);

assert.deepEqual(errors, []);
console.log("ui persistence: ok");
await browser.close(); server.close();
