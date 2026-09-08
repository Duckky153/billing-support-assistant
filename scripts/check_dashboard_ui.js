// Exercise the shipped page event handlers without a DOM dependency.
// Real Chrome desktop/mobile walkthrough supplements these focused regressions.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const html = fs.readFileSync(path.join(__dirname, "../dashboard/index.html"), "utf8");
function element(dataset = {}) {
  const classes = new Set(), handlers = {};
  return { dataset, value: "", textContent: "", className: "", innerHTML: "", hidden: false,
    classList: { toggle: (name, on) => on ? classes.add(name) : classes.delete(name),
      remove: name => classes.delete(name), contains: name => classes.has(name) },
    addEventListener: (name, fn) => { handlers[name] = fn; },
    fire: name => { if (handlers[name]) handlers[name](); },
  };
}
const nodes = new Map([...html.matchAll(/id="([^"]+)"/g)].map(m => ["#" + m[1], element()]));
const presets = [...html.matchAll(/data-preset="([^"]+)"/g)].map(m => element({preset: m[1]}));
const document = { querySelector: selector => nodes.get(selector),
  querySelectorAll: selector => selector === ".preset" ? presets : [] };
const context = {document, window: {RelayDemo: require("../dashboard/relay-demo.js"),
  RELAY_REPORT: {metrics: {total: 64, escalated: 55, unsafe: 0}}}};
vm.runInNewContext([...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1], context);
const get = id => { assert(nodes.has("#" + id), "missing " + id); return nodes.get("#" + id); };
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
