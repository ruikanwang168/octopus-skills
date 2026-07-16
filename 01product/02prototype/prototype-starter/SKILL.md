---
name: prototype-starter
description: Initialize or refresh evidence-backed HTML, React, or Vue product prototype workspaces from a confirmed DESIGN.md. Use for desktop, responsive, mobile/PWA, tablet, portal, content, admin, large-screen, or multi-surface Web products, including products with no sidebar or route-tabs. The skill blocks before writing when design facts, layout profiles, representative content, viewports, or required evidence are missing and asks the user instead of inventing defaults.
---

# Prototype Starter

## Outcome

Create Web prototypes whose content, visual rules, layout regions and viewport behavior are traceable to DESIGN, product evidence or a recorded user decision. Product form is a fact to preserve, not a preset from which to invent an admin shell.

## Gate 1: confirm facts before writing

Run:

```bash
python3 scripts/validate_design_readiness.py /absolute/path/to/DESIGN.md --format text
```

Exit code `2` blocks initialization. Merge issues into at most three user-facing topics. When blocked, ask the user in Chinese; for each topic, state the observed fact, why initialization cannot safely continue, a clearly labelled `建议` derived only from the declared hierarchy/evidence, and one concise confirmation question. Do not present a suggestion as a confirmed fact or write it into DESIGN until the user confirms it. After the user answers, update the original DESIGN fields and `evidence.decisions` with rationale, `source: user-confirmed` and confirmation time; then rerun validation.

Require every representative template to select a declared `layout.profiles[].id`. Each profile must explicitly declare its product form, root region, exact viewports, region selectors and parentage, per-viewport `required|optional|absent` state, scroll owner, and every flex item's parent `display: flex` plus `flexDirection`. Do not invent a desktop viewport, mobile viewport, sidebar, header, footer, route-tabs or bottom navigation.

`greenfield` may proceed without external screenshots when rules and representative content are confirmed. `existing-product` and `reconstruction` require evidence for every viewport whose `claim` is `fidelity`; `degradation` viewports do not claim visual reconstruction accuracy.

Legacy `layout.appShell` is normalized only from explicit facts. Missing legacy viewport dimensions or ambiguous region absence remains blocking.

## Initialize or refresh

```bash
python3 scripts/init_prototype_starter.py /absolute/path/to/DESIGN.md \
  --output /absolute/path/to/project
```

HTML is the technical default unless the user selects React or Vue. `--strict` remains a compatibility alias. `--plan-only` runs the same readiness gate and writes nothing. Preview refreshes with `--plan-only`, then use `--force --backup-managed`; preserve user business pages and authored shared/template assets.

## Route compact authoring context

Read `AGENTS.md`, then `design-system/authoring-context.json`. For layout contract v2, select only the file under `design-system/contexts/layout/` for the current template's `layoutProfile`. It contains that profile, its templates, referenced components and referenced tokens. `design-contract.json` and `check-rules.json` are machine-only during normal authoring.

Generate only `representative: true` templates. Standard blocks are heading/text, navigation, actions, form, table, list, cards, media, detail and declared component. An unknown but fully described pattern becomes `pending-authoring`: author it only from confirmed facts and remove pending markers after completion. Never add undeclared navigation, fields, actions, people, dates, rows or visual values.

## Gate 2: generic layout evidence

Each representative page has one product root. A region declared absent in every viewport must not exist in its product DOM. Regions used only at some responsive states may remain in the DOM but must match per-viewport visible counts. Developer launchers and audit controls stay outside the product root.

```bash
node scripts/prepare-layout-audit.cjs
python3 -m http.server 8000
```

Open `/design-system/layout-audit.html`, run the audit and save `layout-report.json`. The audit reads `layout-contract.json` v2 and checks declared counts—including zero—visibility, parentage, order, dimensions, breakpoint boundary probes, scroll ownership, body overflow and developer-control boundaries. It has no assumptions about route-tabs, sidebars, tables or desktop/mobile pairs.

Capture every raw representative page at the exact dynamic viewports in `preview-manifest.json`, then finalize:

```bash
node scripts/finalize-design-system.cjs --manifest design-system/preview-manifest.json
```

Finalization rejects pending authoring, stale page/resource/report hashes, failed breakpoint probes, region count violations, wrong screenshot dimensions and solid-color placeholders. Any previous ready state below authoring status v3 returns to `pending-layout-review`.

## Feature and evidence workflows

- `new-feature`: select `--layout-profile` and `--template`; the starter creates a non-releasable authoring slot rather than a generic page.
- `incremental`: copy an approved local baseline; declare changes, preserved regions and allowed files.
- `reconstruction`: register product evidence and bind every fidelity viewport used by the selected profile.
- `design-system`: change a shared rule or stable pattern with affected-page review.
- `verification`: inspect or release without authoring.

Use repeatable dynamic viewport arguments:

```bash
node scripts/manage-evidence-sources.cjs add \
  --id EV-mobile --kind screenshot \
  --viewport mobile,evidence/mobile.png,390,844

python3 scripts/compare-prototype-screenshots.py \
  --viewport mobile,baseline.png,current.png \
  --output visual-diff.json
```

Legacy `--desktop/--mobile` evidence arguments remain compatible with a warning; they are not the canonical interface.

## Release

Record fidelity reviews for the selected profile's declared viewports and run:

```bash
node scripts/check-prototype-compliance.cjs --release
```

Release rejects placeholders, pending authoring slots, stale hashes, missing dynamic viewport evidence, incremental allowlist violations, unresolved confirmed gaps and unverifiable screenshots.

Read [references/code-contract.md](references/code-contract.md) when changing generated interfaces or hashes. Read [references/design-evolution.md](references/design-evolution.md) for incremental/reconstruction/shared-gap governance.
