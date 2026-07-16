# Evidence and Design Evolution Contract

Read this reference when reconstructing an existing product, registering evidence, classifying a design gap, updating shared assets, or interpreting a DESIGN refresh impact plan.

## Evidence sources

`design-system/evidence-sources.json` is user-owned and survives refresh. Sources are keyed by stable IDs and contain `kind`, `source`, `productVersion`, `capturedAt`, `browser`, and an arbitrary viewport map with `path`, `sha256`, `format`, `width`, `height`, and `dpr`. Optional `domSnapshot` and `computedStyles` entries use project-local paths and hashes.

Register evidence before a reconstruction manifest references it:

```bash
node scripts/manage-evidence-sources.cjs add \
  --id EV-user-list-v3 --kind product-url --source https://product.example/users \
  --product-version v3 --browser chromium \
  --viewport desktop,evidence/source-desktop.png,1440,900 \
  --viewport mobile,evidence/source-mobile.png,390,844
```

Run `list` to inspect entries and `verify [--id ID]` to recheck hashes and dimensions.

## Reconstruction contract

Use `mode: "reconstruction"` only when product evidence exists and no approved local prototype page/component can serve as a byte-identifiable baseline. Each confirmed page requires `evidenceRefs`. Release requires `reconstruction-authored`, reference/current evidence for every fidelity viewport in the selected layout profile, and a passing reconstruction comparison report.

Incremental and reconstruction masks have different meanings:

- `changeMasks` cover requested changes in an incremental upgrade.
- `unstableMasks` cover timestamps, animation, random data, or other non-deterministic evidence in either mode.
- Reconstruction rejects `changeMasks` because the product reference, not a requested delta, is the target.

## Design gap schema and state machine

`design-system/design-gaps.json` is user-owned. Each gap contains:

```json
{
  "id": "DG-003",
  "status": "classified",
  "classification": "shared-gap",
  "scope": "shared",
  "observed": "Two list pages use the same collapsible filter panel.",
  "evidenceRefs": ["EV-user-list-v3", "EV-order-list-v3"],
  "affectedPageKeys": ["user-list", "order-list"],
  "proposedChange": "Promote collapsible-filter-panel",
  "resolution": null,
  "verification": null
}
```

Classifications are `implementation-defect`, `feature-local`, `shared-gap`, `design-gap`, and `evidence-conflict`.

Allowed transitions are:

```text
observed → classified → confirmed → applied → verified
    └──────────────→ rejected / waived
verified / rejected / waived → observed (reopen with reason)
```

Applying a `shared-gap` requires registered shared references whose entries include `usedBy`. Applying a `design-gap` requires `--design-source-sha` matching the refreshed design contract, proving DESIGN was updated/refreshed before verification. A single unconfirmed observation never changes DESIGN automatically.

In release mode, `confirmed` and `applied` gaps block their `affectedPageKeys`. `observed` and `classified` gaps warn. `verified`, `rejected`, and `waived` gaps do not block.

## Design change impact

Contract v4 contains `runtimeHashes.tokens|shell|components|patterns|rules`; `designRuntimeSha256` remains their aggregate. Reviews record `designDomains`, `sharedRefs`, and `designProfileSha256`. Missing v4 metadata means all-domain dependency.

`design-change-plan.json` compares previous/current domain hashes and lists `changedDomains`, `affectedPageKeys`, `affectedSharedRefs`, and `requiredActions`. Token or shell changes are global. Other domain changes affect reviews declaring those domains. When registry ownership is incomplete, keep the broader conservative review requirement.
