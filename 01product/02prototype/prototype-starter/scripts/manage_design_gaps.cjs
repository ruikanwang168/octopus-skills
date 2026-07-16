#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const gapFile = path.join(root, "design-system", "design-gaps.json");
const evidenceFile = path.join(root, "design-system", "evidence-sources.json");
const registryFile = path.join(root, "design-system", "shared-registry.json");
const contractFile = path.join(root, "design-system", "design-contract.json");
const args = process.argv.slice(2);
const command = args.shift();
const options = {};
for (let index = 0; index < args.length; index += 1) {
  if (args[index].startsWith("--")) { options[args[index].slice(2)] = args[index + 1]; index += 1; }
}
const fail = (message) => { console.error(`ERROR ${message}`); process.exit(1); };
const read = (file, fallback) => { try { return JSON.parse(fs.readFileSync(file, "utf8")); } catch (_) { return fallback; } };
const split = (value) => String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
const ledger = read(gapFile, { version: 1, gaps: {} });
ledger.version = 1;
ledger.gaps = ledger.gaps && typeof ledger.gaps === "object" ? ledger.gaps : {};
const evidence = read(evidenceFile, { sources: {} }).sources || {};
const classifications = new Set(["implementation-defect", "feature-local", "shared-gap", "design-gap", "evidence-conflict"]);
const transitions = {
  observed: new Set(["classified", "rejected", "waived"]),
  classified: new Set(["confirmed", "rejected", "waived"]),
  confirmed: new Set(["applied", "rejected", "waived"]),
  applied: new Set(["verified", "waived"]),
  verified: new Set(["observed"]),
  rejected: new Set(["observed"]),
  waived: new Set(["observed"]),
};
const write = () => fs.writeFileSync(gapFile, JSON.stringify(ledger, null, 2) + "\n");
const requireGap = () => {
  const gap = ledger.gaps[options.id];
  if (!gap) fail(`unknown design gap ${options.id || ""}`);
  return gap;
};
const validateEvidence = (refs) => {
  for (const ref of refs) if (!evidence[ref]) fail(`unknown evidence reference ${ref}`);
};
const transition = (gap, next) => {
  if (!transitions[gap.status] || !transitions[gap.status].has(next)) fail(`invalid transition ${gap.status} -> ${next}`);
  gap.status = next;
  gap.updatedAt = new Date().toISOString();
};

if (command === "list") {
  const status = options.status;
  for (const gap of Object.values(ledger.gaps)) if (!status || gap.status === status) console.log(`${gap.id}\t${gap.status}\t${gap.classification || ""}\t${gap.observed}`);
  process.exit(0);
}
if (command === "observe") {
  if (!options.id || !options.observed) fail("observe requires --id and --observed");
  if (ledger.gaps[options.id]) fail(`design gap already exists: ${options.id}`);
  const evidenceRefs = split(options.evidence);
  validateEvidence(evidenceRefs);
  ledger.gaps[options.id] = {
    id: options.id,
    status: "observed",
    classification: "",
    scope: options.scope || "page",
    observed: options.observed,
    evidenceRefs,
    affectedPageKeys: split(options.pages),
    proposedChange: options.proposal || "",
    resolution: null,
    verification: null,
    designSourceSha256: (() => {
      const contract = read(contractFile, {});
      return contract.sourceSha256 || (contract.meta && contract.meta.sourceSha256) || "";
    })(),
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
  write();
  console.log(`Observed design gap ${options.id}.`);
  process.exit(0);
}
const gap = requireGap();
if (command === "classify") {
  if (!classifications.has(options.classification)) fail(`unsupported classification ${options.classification || ""}`);
  const refs = split(options.evidence).length ? split(options.evidence) : gap.evidenceRefs;
  if (!refs.length) fail("classification requires at least one evidence reference");
  validateEvidence(refs);
  gap.classification = options.classification;
  gap.evidenceRefs = refs;
  gap.affectedPageKeys = split(options.pages).length ? split(options.pages) : gap.affectedPageKeys;
  gap.proposedChange = options.proposal || gap.proposedChange;
  transition(gap, "classified");
} else if (command === "confirm") {
  if (!gap.classification) fail("classify the gap before confirmation");
  if (!Array.isArray(gap.affectedPageKeys) || gap.affectedPageKeys.length === 0) fail("confirmation requires affected page keys");
  transition(gap, "confirmed");
} else if (command === "apply") {
  if (!options.files) fail("apply requires --files");
  if (gap.classification === "shared-gap") {
    const refs = split(options["registry-refs"]);
    if (!refs.length) fail("shared-gap apply requires --registry-refs");
    const registry = read(registryFile, {});
    for (const ref of refs) {
      const [section, name] = ref.split(".", 2);
      const entry = registry[section] && registry[section][name];
      if (!entry || !Array.isArray(entry.usedBy) || entry.usedBy.length === 0) fail(`shared registry reference requires usedBy: ${ref}`);
    }
    gap.registryRefs = refs;
  }
  if (gap.classification === "design-gap") {
    const contract = read(contractFile, {});
    const currentSource = contract.sourceSha256 || (contract.meta && contract.meta.sourceSha256) || "";
    if (!options["design-source-sha"] || options["design-source-sha"] !== currentSource) fail("design-gap apply requires --design-source-sha matching the refreshed DESIGN contract");
    if (gap.designSourceSha256 && gap.designSourceSha256 === currentSource) fail("design-gap apply requires DESIGN to change after the gap was observed");
  }
  gap.resolution = { type: options.type || gap.classification, files: split(options.files), note: options.note || "", appliedAt: new Date().toISOString() };
  transition(gap, "applied");
} else if (command === "verify") {
  if (!options.evidence) fail("verify requires --evidence");
  const refs = split(options.evidence);
  validateEvidence(refs);
  gap.verification = { evidenceRefs: refs, pageKeys: split(options.pages).length ? split(options.pages) : gap.affectedPageKeys, verifiedAt: new Date().toISOString() };
  transition(gap, "verified");
} else if (["reject", "waive"].includes(command)) {
  if (!options.reason) fail(`${command} requires --reason`);
  gap.decision = { reason: options.reason, at: new Date().toISOString() };
  transition(gap, command === "reject" ? "rejected" : "waived");
} else if (command === "reopen") {
  if (!options.reason) fail("reopen requires --reason");
  gap.reopened = { reason: options.reason, at: new Date().toISOString() };
  transition(gap, "observed");
} else {
  fail("usage: manage-design-gaps.cjs observe|classify|confirm|apply|verify|reject|waive|reopen|list");
}
write();
console.log(`Updated design gap ${gap.id} -> ${gap.status}.`);
