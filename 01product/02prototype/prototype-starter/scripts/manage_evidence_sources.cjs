#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const root = path.resolve(__dirname, "..");
const ledgerFile = path.join(root, "design-system", "evidence-sources.json");
const args = process.argv.slice(2);
const command = args.shift();
const options = {};
for (let index = 0; index < args.length; index += 1) {
  const value = args[index];
  if (!value.startsWith("--")) continue;
  const name = value.slice(2);
  const next = args[index + 1];
  if (name === "viewport") {
    options.viewport = options.viewport || [];
    options.viewport.push(next);
  } else {
    options[name] = next;
  }
  index += 1;
}

const sha = (file) => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
const fail = (message) => { console.error(`ERROR ${message}`); process.exit(1); };
const readLedger = () => {
  try { return JSON.parse(fs.readFileSync(ledgerFile, "utf8")); }
  catch (_) { return { version: 2, sources: {} }; }
};
const insideFile = (value, label) => {
  if (!value) fail(`missing ${label}`);
  const absolute = path.resolve(root, value);
  const relative = path.relative(root, absolute).replaceAll(path.sep, "/");
  if (relative.startsWith("../") || path.isAbsolute(relative) || !fs.existsSync(absolute) || !fs.statSync(absolute).isFile()) fail(`${label} must be an existing project file: ${value}`);
  return { absolute, relative };
};
const imageSize = (file) => {
  const data = fs.readFileSync(file);
  if (data.length >= 24 && data.subarray(0, 8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) return { format: "png", width: data.readUInt32BE(16), height: data.readUInt32BE(20) };
  if (data.length >= 12 && data.subarray(0, 4).toString() === "RIFF" && data.subarray(8, 12).toString() === "WEBP" && data.subarray(12, 16).toString() === "VP8X" && data.length >= 30) return { format: "webp", width: 1 + data.readUIntLE(24, 3), height: 1 + data.readUIntLE(27, 3) };
  if (data.length >= 4 && data[0] === 0xff && data[1] === 0xd8) {
    let offset = 2;
    while (offset + 9 < data.length) {
      if (data[offset] !== 0xff) { offset += 1; continue; }
      const marker = data[offset + 1], length = data.readUInt16BE(offset + 2);
      if ([0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf].includes(marker)) return { format: "jpeg", width: data.readUInt16BE(offset + 7), height: data.readUInt16BE(offset + 5) };
      if (!length) break;
      offset += 2 + length;
    }
  }
  fail(`${path.basename(file)} must be a supported PNG, JPEG, or WebP image`);
};
const makeViewport = (id, fileValue, widthValue, heightValue, dprValue = 1) => {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(id)) fail(`invalid viewport id: ${id}`);
  const item = insideFile(fileValue, `viewport ${id}`), size = imageSize(item.absolute);
  const width = Number(widthValue), height = Number(heightValue), dpr = Number(dprValue || 1);
  if (!(width > 0) || !(height > 0) || !(dpr > 0)) fail(`viewport ${id} requires positive width, height and dpr`);
  if (size.width !== width || size.height !== height) fail(`${id} screenshot is ${size.width}x${size.height}, expected ${width}x${height}`);
  return { path: item.relative, sha256: sha(item.absolute), format: size.format, width, height, dpr };
};
const parseViewports = () => {
  const result = {};
  for (const spec of options.viewport || []) {
    const [id, file, width, height, dpr] = String(spec || "").split(",");
    if (!id || !file || !width || !height) fail("--viewport format is id,path,width,height[,dpr]");
    result[id] = makeViewport(id, file, width, height, dpr);
  }
  if (!Object.keys(result).length && (options.desktop || options.mobile)) {
    console.warn("WARN --desktop/--mobile are compatibility arguments; prefer repeatable --viewport id,path,width,height[,dpr]");
    if (options.desktop) result.desktop = makeViewport("desktop", options.desktop, options["desktop-width"] || 1440, options["desktop-height"] || 900, options["desktop-dpr"] || 1);
    if (options.mobile) result.mobile = makeViewport("mobile", options.mobile, options["mobile-width"] || 390, options["mobile-height"] || 844, options["mobile-dpr"] || 1);
  }
  if (!Object.keys(result).length) fail("add requires at least one --viewport id,path,width,height[,dpr]");
  return result;
};
const verifySource = (source) => {
  const entries = Object.entries(source.viewports || {});
  if (!entries.length) fail(`${source.id} has no viewport evidence`);
  for (const [id, entry] of entries) {
    const item = insideFile(entry.path, `${source.id}.${id}`), size = imageSize(item.absolute);
    if (size.width !== Number(entry.width) || size.height !== Number(entry.height)) fail(`${source.id}.${id} dimensions changed`);
    if (sha(item.absolute) !== entry.sha256) fail(`${source.id}.${id} evidence changed`);
  }
};
const optionalProjectFile = (value, label) => {
  if (!value) return null;
  const item = insideFile(value, label);
  return { path: item.relative, sha256: sha(item.absolute) };
};

const ledger = readLedger();
ledger.version = 2;
ledger.sources = ledger.sources && typeof ledger.sources === "object" ? ledger.sources : {};
if (command === "list") {
  for (const source of Object.values(ledger.sources)) console.log(`${source.id}\t${source.kind}\t${Object.keys(source.viewports || {}).join(",")}\t${source.source || ""}`);
  process.exit(0);
}
if (command === "verify") {
  const selected = options.id ? [ledger.sources[options.id]] : Object.values(ledger.sources);
  if (selected.some((item) => !item)) fail(`unknown evidence source ${options.id}`);
  for (const source of selected) verifySource(source);
  console.log(`Verified ${selected.length} evidence source(s).`);
  process.exit(0);
}
if (command !== "add") fail("usage: manage-evidence-sources.cjs add|list|verify");
if (!options.id || !/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(options.id)) fail("add requires a stable --id");
const kinds = new Set(["screenshot", "product-url", "source-code", "approved-prototype", "recording"]);
if (!kinds.has(options.kind)) fail(`unsupported evidence kind: ${options.kind || ""}`);
const source = {
  id: options.id,
  kind: options.kind,
  source: options.source || "",
  productVersion: options["product-version"] || "",
  capturedAt: options["captured-at"] || new Date().toISOString(),
  browser: options.browser || "unspecified",
  viewports: parseViewports(),
  domSnapshot: optionalProjectFile(options["dom-snapshot"], "dom-snapshot"),
  computedStyles: optionalProjectFile(options["computed-styles"], "computed-styles"),
  updatedAt: new Date().toISOString(),
};
verifySource(source);
ledger.sources[source.id] = source;
fs.writeFileSync(ledgerFile, JSON.stringify(ledger, null, 2) + "\n");
console.log(`Updated evidence source ${source.id}.`);
