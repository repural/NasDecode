#!/usr/bin/env node
// Populate historical QQQ reactions from Massive one-minute aggregate bars.
// Usage: MASSIVE_API_KEY=... node scripts/fill-qqq-reactions.mjs
// Optional: --dry-run, --date=YYYY-MM-DD, --bars-dir=/path/to/exported/json
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const file = new URL("../public/event-results.json", import.meta.url);
const results = JSON.parse(await readFile(file, "utf8"));
const args = process.argv.slice(2);
const dryRun = args.includes("--dry-run");
const dateFilter = args.find(arg => arg.startsWith("--date="))?.slice(7);
const barsDir = args.find(arg => arg.startsWith("--bars-dir="))?.slice(11);
const apiKey = process.env.MASSIVE_API_KEY;
if (!barsDir && !apiKey) {
  console.error("MASSIVE_API_KEY is required (or --bars-dir for saved Massive responses).");
  process.exit(2);
}

// Future historical results with a precise ET time are picked up automatically.
// Composite days and approximate earnings times are excluded until split into
// independently timed event records.
const times = Object.fromEntries(Object.entries(results.eventIndex)
  .filter(([, entry]) => /^\d{2}:\d{2}$/.test(entry.timeET))
  .map(([eventId, entry]) => [eventId, entry.timeET]));
const formatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/New_York", year: "numeric", month: "2-digit",
  day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23"
});
function etParts(utcMs) {
  const fields = Object.fromEntries(formatter.formatToParts(new Date(utcMs)).map(p => [p.type, p.value]));
  return { date: `${fields.year}-${fields.month}-${fields.day}`, time: `${fields.hour}:${fields.minute}` };
}
function eventUtc(date, time) {
  const [hour, minute] = time.split(":").map(Number);
  const approx = Date.parse(`${date}T${time}:00Z`);
  for (let utc = approx; utc <= approx + 6 * 3600000; utc += 60000) {
    const et = etParts(utc);
    if (et.date === date && et.time === time) return utc;
  }
  throw new Error(`Could not resolve Eastern time for ${date} ${time}`);
}
function barAt(bars, minuteStart) {
  return bars.find(bar => bar.t === minuteStart && Number.isFinite(bar.c));
}
function reaction(bars, releaseUtc, minutes) {
  // Bar timestamps mark the start of their minute; the 09:59 close is the
  // 10:00 checkpoint. Do not substitute an older/nearby bar for a missing one.
  const before = barAt(bars, releaseUtc - 60000);
  const after = barAt(bars, releaseUtc + (minutes - 1) * 60000);
  if (!before || !after) return null;
  return {
    pct: Math.round(((after.c / before.c) - 1) * 10000) / 100,
    before: { minuteET: etParts(before.t).time, close: before.c },
    after: { minuteET: etParts(after.t).time, close: after.c }
  };
}
async function barsFor(date) {
  if (barsDir) {
    const data = JSON.parse(await readFile(path.join(barsDir, `${date}.json`), "utf8"));
    return data.results ?? [];
  }
  const url = new URL(`https://api.massive.com/v2/aggs/ticker/QQQ/range/1/minute/${date}/${date}`);
  url.searchParams.set("adjusted", "true");
  url.searchParams.set("sort", "asc");
  url.searchParams.set("limit", "5000");
  // Authorization header keeps the key out of URLs, logs, and stored output.
  let response;
  for (let attempt = 0; attempt < 4; attempt++) {
    response = await fetch(url, { headers: { Authorization: `Bearer ${apiKey}` } });
    if (response.status !== 429 || attempt === 3) break;
    const retryAfter = Number(response.headers.get("retry-after"));
    const delay = Number.isFinite(retryAfter) && retryAfter > 0
      ? Math.min(retryAfter * 1000, 90000)
      : 30000 * (attempt + 1);
    console.log(`Massive rate limit on ${date}; retrying in ${Math.ceil(delay / 1000)}s`);
    await new Promise(resolve => setTimeout(resolve, delay));
  }
  if (!response.ok) throw new Error(`Massive HTTP ${response.status} for ${date}`);
  const data = await response.json();
  if (data.status !== "OK" || data.next_url) throw new Error(`Incomplete Massive minute bars for ${date}`);
  return data.results ?? [];
}
const eligible = results.results.filter(item => times[item.eventId] && (!dateFilter || item.eventId.startsWith(dateFilter)));
const dates = [...new Set(eligible.map(item => item.eventId.slice(0, 10)))];
const byDate = new Map();
for (const [index, date] of dates.entries()) {
  if (index && !barsDir) await new Promise(resolve => setTimeout(resolve, 14000));
  byDate.set(date, await barsFor(date));
}
let filled = 0;
for (const item of eligible) {
  const date = item.eventId.slice(0, 10);
  const releaseUtc = eventUtc(date, times[item.eventId]);
  const bars = byDate.get(date);
  const at15 = reaction(bars, releaseUtc, 15);
  const at60 = reaction(bars, releaseUtc, 60);
  if (!at15 && !at60) {
    console.log(`${item.eventId}: no exact minute bars for requested checkpoints; unchanged`);
    continue;
  }
  item.qqq15m = at15 ? `${at15.pct > 0 ? "+" : ""}${at15.pct.toFixed(2)}%` : null;
  item.qqq1h = at60 ? `${at60.pct > 0 ? "+" : ""}${at60.pct.toFixed(2)}%` : null;
  item.qqqReaction = {
    source: "Massive QQQ adjusted one-minute aggregate bars",
    sourceUrl: "https://massive.com/docs/rest/stocks/aggregates/custom-bars",
    releaseTimeET: times[item.eventId],
    method: "Last completed one-minute bar before release versus last completed bar at +15m / +60m; close-to-close percent change. Measures QQQ, not Nasdaq Composite.",
    at15, at60
  };
  filled++;
  console.log(`${item.eventId}: ${item.qqq15m ?? "—"} / ${item.qqq1h ?? "—"}`);
}
if (filled && !dryRun) {
  results.lastUpdated = new Date().toISOString().slice(0, 10);
  await writeFile(file, JSON.stringify(results, null, 2) + "\n");
}
console.log(`${filled} verified QQQ reactions ${dryRun ? "calculated (dry run)" : "saved"}`);
