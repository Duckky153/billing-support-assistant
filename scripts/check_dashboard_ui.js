// Exercise the shipped page event handlers without a DOM dependency.
// Real Chrome desktop/mobile walkthrough supplements these focused regressions.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const html = fs.readFileSync(path.join(__dirname, "../dashboard/index.html"), "utf8");
function element(dataset = {}) {
  const classes = new Set(), handlers = {};
  const children = [];
  return { dataset, value: "", textContent: "", className: "", innerHTML: "", hidden: false, children,
    append: (...items) => children.push(...items), replaceWith: () => {},
    attributes: {}, setAttribute(name, value) { this.attributes[name] = value; },
    classList: { toggle: (name, on) => on ? classes.add(name) : classes.delete(name),
      remove: name => classes.delete(name), contains: name => classes.has(name) },
    addEventListener: (name, fn) => { handlers[name] = fn; },
    fire: name => { if (handlers[name]) handlers[name](); },
  };
}
const nodes = new Map([...html.matchAll(/id="([^"]+)"/g)].map(m => ["#" + m[1], element()]));
const presets = [...html.matchAll(/data-preset="([^"]+)"/g)].map(m => element({preset: m[1]}));
const document = { querySelector: selector => nodes.get(selector), createElement: () => element(),
  querySelectorAll: selector => selector === ".preset" ? presets : [] };
const reportWindow = {};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../dashboard/report-data.js"), "utf8"), {window: reportWindow});
const report = reportWindow.BILLING_SUPPORT_REPORT;
const context = {document, window: {BillingSupportDemo: require("../dashboard/billing-support-demo.js"),
  BILLING_SUPPORT_REPORT: report}};
vm.runInNewContext([...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1], context);
const get = id => { assert(nodes.has("#" + id), "missing " + id); return nodes.get("#" + id); };
// The results table has one row per ticket type, and the rows add up to the summary.
const rows = get("results-body").children;
assert.equal(rows.length, Object.keys(report.by_category).length);
assert.equal(rows.reduce((sum, tr) => sum + Number(tr.children[1].textContent), 0), report.metrics.total);
assert(rows.every(tr => !tr.children[0].textContent.includes("_")), "every ticket type has a readable label");
assert.equal(get("metric-resolved").textContent, report.metrics.resolved);
assert.match(get("customer-records").textContent, /in_ada1/);
presets.find(p => p.dataset.preset === "question").fire("click");
assert.equal(get("result-status").textContent, "Answered");
assert.equal(presets.find(p => p.dataset.preset === "question").attributes["aria-pressed"], "true");
presets.find(p => p.dataset.preset === "negated").fire("click");
assert.equal(get("result-executed").textContent, "No");
presets.find(p => p.dataset.preset === "cancel").fire("click");
assert.equal(get("result-executed").textContent, "Yes");
presets.find(p => p.dataset.preset === "question").fire("click");
assert.match(get("result-reply").textContent, /2025-02-11/);
get("ticket").value = "Do not cancel my subscription. When does it renew?";
get("ticket").fire("input");
assert.equal(get("result-status").textContent, "Not checked");
assert.equal(get("result-executed").textContent, "—");
assert(presets.every(p => !p.classList.contains("active")));
get("run").fire("click");
assert.equal(get("result-executed").textContent, "No");
assert.match(get("result-handoff").textContent, /human|review/);
get("customer").value = "cus_erin";
get("customer").fire("change");
assert.equal(get("result-status").textContent, "Not checked");
console.log("dashboard event regressions passed");
