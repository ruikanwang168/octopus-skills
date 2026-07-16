#!/usr/bin/env python3
"""Legacy scaffold for older framework-specific page-spec skeletons.

New Markdown-first projects should use init_spec_system.py and the references
in markdown-spec-format.md / framework-integration.md instead. This generator
is retained for migration support and older JSON-based skeletons.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from init_spec_system import detect_spec_dir, init_project


REGISTRY_KEYS_MARKER = "  // __PAGE_SPEC_KEYS__"
REGISTRY_ROUTES_MARKER = "  // __PAGE_SPEC_ROUTES__"


@dataclass
class WriteResult:
    path: Path
    status: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scaffold React / Vue / HTML page-spec architecture from the built-in skeletons."
    )
    parser.add_argument("--root", required=True, help="Target project root.")
    parser.add_argument(
        "--framework",
        required=True,
        choices=("react", "vue", "html"),
        help="Target framework family.",
    )
    parser.add_argument(
        "--layout",
        required=True,
        choices=("fixed-shell", "document-flow"),
        help="Skeleton layout mode.",
    )
    parser.add_argument("--page-key", required=True, help="Stable page key, for example `market`.")
    parser.add_argument(
        "--page-name",
        help="Human-facing page name. Defaults to a titleized version of --page-key.",
    )
    parser.add_argument(
        "--route-path",
        help="Explicit route path for framework registries. Defaults to `/<page-key>`.",
    )
    parser.add_argument(
        "--component-name",
        help="Optional React/Vue component name for the integration example.",
    )
    parser.add_argument(
        "--html-file",
        help="Optional HTML example filename. Defaults to `<page-key>.page-spec.<mode>.example.html`.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite generated files when they already exist.",
    )
    return parser.parse_args()


def to_pascal_case(value: str) -> str:
    parts = [part for part in value.replace("_", "-").split("-") if part]
    return "".join(part[:1].upper() + part[1:] for part in parts) or "PageSpec"


def to_camel_case(value: str) -> str:
    pascal = to_pascal_case(value)
    return pascal[:1].lower() + pascal[1:] if pascal else "pageSpec"


def default_page_name(page_key: str) -> str:
    return page_key.replace("-", " ").replace("_", " ").title()


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str, force: bool) -> WriteResult:
    ensure_directory(path.parent)
    normalized = content.rstrip() + "\n"
    if path.exists() and not force:
        existing = path.read_text(encoding="utf-8")
        if existing == normalized:
            return WriteResult(path=path, status="unchanged")
        return WriteResult(path=path, status="skipped")

    path.write_text(normalized, encoding="utf-8")
    return WriteResult(path=path, status="written")


def ensure_marker_block(path: Path, marker: str, line: str, force: bool) -> WriteResult:
    ensure_directory(path.parent)
    if not path.exists() or force:
        base = react_or_vue_registry_template()
        path.write_text(base, encoding="utf-8")

    content = path.read_text(encoding="utf-8")
    if line in content:
        return WriteResult(path=path, status="unchanged")
    if marker not in content:
        return WriteResult(path=path, status="skipped")

    updated = content.replace(marker, f"{line}\n{marker}")
    path.write_text(updated, encoding="utf-8")
    return WriteResult(path=path, status="updated")


def ensure_history_slot(spec_root: Path, page_key: str) -> WriteResult:
    history_dir = spec_root / "history" / page_key
    ensure_directory(history_dir)
    sentinel = history_dir / ".gitkeep"
    if sentinel.exists():
        return WriteResult(path=sentinel, status="unchanged")
    sentinel.write_text("", encoding="utf-8")
    return WriteResult(path=sentinel, status="written")


def react_or_vue_schema_template() -> str:
    return """export interface PageSpecField {
  id: string;
  name: string;
  value?: string;
  required?: boolean;
  description?: string;
}

export interface PageSpecSection {
  id: string;
  title: string;
  rules: string[];
  fields?: PageSpecField[];
}

export interface PageSpecMeta {
  sourceType: "generated" | "manual" | "mixed";
  lastGeneratedAt: string | null;
  lastManualEditedAt: string | null;
  overwriteProtected: boolean;
  specId: string;
  batchId: string;
}

export interface PageSpec {
  pageKey: string;
  version: number;
  pageName: string;
  pageType: string;
  pageShape: string;
  summary: string;
  secondarySurfaces?: string[];
  sections: PageSpecSection[];
  meta: PageSpecMeta;
}
"""


def react_or_vue_registry_template() -> str:
    return f"""export const PAGE_SPEC_KEYS = {{
{REGISTRY_KEYS_MARKER}
}} as const;

export type PageSpecKey = (typeof PAGE_SPEC_KEYS)[keyof typeof PAGE_SPEC_KEYS];

export const PAGE_SPEC_ROUTE_MAP = {{
{REGISTRY_ROUTES_MARKER}
}} as const;

export type PageSpecRoute = keyof typeof PAGE_SPEC_ROUTE_MAP;

export function resolvePageSpecKey(pathname: string): PageSpecKey | null {{
  const route = pathname as PageSpecRoute;
  return PAGE_SPEC_ROUTE_MAP[route] ?? null;
}}
"""


def react_or_vue_index_template() -> str:
    return """import type { PageSpec } from "./schema";
import type { PageSpecKey } from "./registry";

const bundledModules = import.meta.glob("./current/*.json", {
  eager: true,
  import: "default",
}) as Record<string, PageSpec>;

export async function loadPageSpec(pageKey: PageSpecKey): Promise<PageSpec | null> {
  try {
    const response = await fetch(`/api/page-specs/${pageKey}`);
    if (!response.ok) {
      throw new Error(`Failed to load page spec: ${response.status}`);
    }
    return (await response.json()) as PageSpec;
  } catch {
    return bundledModules[`./current/${pageKey}.json`] ?? null;
  }
}

export async function savePageSpec(pageKey: PageSpecKey, spec: PageSpec): Promise<void> {
  const response = await fetch(`/api/page-specs/${pageKey}/save`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(spec),
  });

  if (!response.ok) {
    throw new Error(`Failed to save page spec: ${response.status}`);
  }
}

export function clonePageSpec(spec: PageSpec): PageSpec {
  return JSON.parse(JSON.stringify(spec)) as PageSpec;
}
"""


def react_use_page_spec_template() -> str:
    return """import { useEffect, useState } from "react";

import { loadPageSpec } from "./index";
import type { PageSpecKey } from "./registry";
import type { PageSpec } from "./schema";

export function usePageSpec(pageKey: PageSpecKey) {
  const [spec, setSpec] = useState<PageSpec | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      setLoading(true);
      setError(null);

      try {
        const nextSpec = await loadPageSpec(pageKey);
        if (!cancelled) {
          setSpec(nextSpec);
        }
      } catch (value) {
        if (!cancelled) {
          setSpec(null);
          setError(value instanceof Error ? value : new Error("Failed to load page spec."));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, [pageKey, revision]);

  return {
    spec,
    loading,
    error,
    reload: () => setRevision((value) => value + 1),
  };
}
"""


def react_page_spec_doc_template(inline: bool) -> str:
    component_name = "PageSpecDocInline" if inline else "PageSpecDoc"
    props_type = "pageKey: PageSpecKey" if inline else "pageKey: PageSpecKey; onBackToPage?: () => void"
    back_button = "" if inline else """        <button type="button" onClick={onBackToPage}>
          返回产品页
        </button>
"""
    margin_class = " proto-spec-doc--inline" if inline else ""
    on_back_param = "" if inline else ", onBackToPage"
    return f"""import type {{ PageSpecKey }} from "../page-specs/registry";
import {{ usePageSpec }} from "../page-specs/usePageSpec";

type Props = {{
  {props_type};
}};

export function {component_name}({{ pageKey{on_back_param} }}: Props) {{
  const {{ spec, loading, error, reload }} = usePageSpec(pageKey);

  if (loading) {{
    return (
      <section className="proto-spec-doc{margin_class}" data-role="page-spec">
        加载需求说明...
      </section>
    );
  }}

  if (error) {{
    return (
      <section className="proto-spec-doc{margin_class}" data-role="page-spec">
        <header className="proto-spec-doc__header">
          <h2>需求说明加载失败</h2>
          <button type="button" onClick={{reload}}>
            重试
          </button>
        </header>
        <p>{{error.message}}</p>
      </section>
    );
  }}

  if (!spec) {{
    return null;
  }}

  return (
    <section
      className="proto-spec-doc{margin_class}"
      data-role="page-spec"
      data-spec-origin="prototype-spec-annotator"
      data-spec-page={{pageKey}}
      data-spec-id={{`${{pageKey}}-spec`}}
      data-spec-batch={{spec.meta.batchId}}
      data-spec-visible="true"
    >
      <header className="proto-spec-doc__header">
        <div>
          <p className="proto-spec-doc__eyebrow">Requirement Spec</p>
          <h2>{{spec.pageName}} 页面规则说明</h2>
          <p>{{spec.summary}}</p>
        </div>
{back_button}      </header>

      {{spec.secondarySurfaces?.length ? (
        <section className="proto-spec-doc__surface-list">
          <h3>二级承载面</h3>
          <ul>
            {{spec.secondarySurfaces.map((item) => (
              <li key={{item}}>{{item}}</li>
            ))}}
          </ul>
        </section>
      ) : null}}

      <div className="proto-spec-doc__sections">
        {{spec.sections.map((section) => (
          <article key={{section.id}} className="proto-spec-doc__section">
            <h3>{{section.title}}</h3>
            <ol>
              {{section.rules.map((rule, index) => (
                <li key={{`${{section.id}}-${{index}}`}}>{{rule}}</li>
              ))}}
            </ol>
            {{section.fields?.length ? (
              <table className="proto-spec-doc__fields">
                <thead>
                  <tr>
                    <th>字段</th>
                    <th>说明</th>
                    <th>必填</th>
                  </tr>
                </thead>
                <tbody>
                  {{section.fields.map((field) => (
                    <tr key={{field.id}}>
                      <td>{{field.name}}</td>
                      <td>{{field.description ?? field.value ?? "待补充"}}</td>
                      <td>{{field.required ? "是" : "否"}}</td>
                    </tr>
                  ))}}
                </tbody>
              </table>
            ) : null}}
          </article>
        ))}}
      </div>
    </section>
  );
}}
"""


def react_with_page_spec_template() -> str:
    return """import { useState, type ComponentType } from "react";

import type { PageSpecKey } from "../page-specs/registry";
import { PageSpecDoc } from "./PageSpecDoc";

export function withPageSpec<P extends object>(pageKey: PageSpecKey, Component: ComponentType<P>) {
  const WrappedPage = (props: P) => {
    const [mode, setMode] = useState<"page" | "spec">("page");

    return (
      <div className="proto-spec-shell" data-page-spec-key={pageKey}>
        <header className="proto-spec-shell__toolbar">
          <div className="proto-spec-shell__switcher">
            <button type="button" onClick={() => setMode("page")} aria-pressed={mode === "page"}>
              产品页面
            </button>
            <button type="button" onClick={() => setMode("spec")} aria-pressed={mode === "spec"}>
              需求说明
            </button>
          </div>
        </header>
        <div className="proto-spec-shell__body">
          {mode === "page" ? (
            <Component {...props} />
          ) : (
            <PageSpecDoc pageKey={pageKey} onBackToPage={() => setMode("page")} />
          )}
        </div>
      </div>
    );
  };

  WrappedPage.displayName = `withPageSpec(${Component.displayName || Component.name || pageKey})`;
  return WrappedPage;
}
"""


def react_fixed_shell_example_template(component_name: str, page_key: str) -> str:
    return f"""import {{ withPageSpec }} from "../../components/withPageSpec";
import {{ PAGE_SPEC_KEYS }} from "../registry";

function {component_name}() {{
  return (
    <section className="proto-page-stage">
      <h1>{component_name}</h1>
      <p>TODO: replace this example body with the real page content.</p>
    </section>
  );
}}

export default withPageSpec(PAGE_SPEC_KEYS.{to_camel_case(page_key)}, {component_name});
"""


def react_document_flow_example_template(component_name: str, page_key: str) -> str:
    return f"""import {{ PageSpecDocInline }} from "../../components/PageSpecDocInline";
import {{ PAGE_SPEC_KEYS }} from "../registry";

export default function {component_name}() {{
  return (
    <main className="proto-page-stage">
      <section>
        <h1>{component_name}</h1>
        <p>TODO: replace this example body with the real page content.</p>
      </section>
      <PageSpecDocInline pageKey={{PAGE_SPEC_KEYS.{to_camel_case(page_key)}}} />
    </main>
  );
}}
"""


def vue_use_page_spec_template() -> str:
    return """import { ref, watchEffect } from "vue";

import { loadPageSpec } from "./index";
import type { PageSpecKey } from "./registry";
import type { PageSpec } from "./schema";

export function usePageSpec(getPageKey: () => PageSpecKey) {
  const spec = ref<PageSpec | null>(null);
  const loading = ref(true);
  const error = ref<Error | null>(null);
  const revision = ref(0);

  function reload() {
    revision.value += 1;
  }

  watchEffect((onCleanup) => {
    const pageKey = getPageKey();
    revision.value;

    let cancelled = false;
    loading.value = true;
    error.value = null;

    void loadPageSpec(pageKey)
      .then((nextSpec) => {
        if (!cancelled) {
          spec.value = nextSpec;
        }
      })
      .catch((value) => {
        if (!cancelled) {
          spec.value = null;
          error.value = value instanceof Error ? value : new Error("Failed to load page spec.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          loading.value = false;
        }
      });

    onCleanup(() => {
      cancelled = true;
    });
  });

  return { spec, loading, error, reload };
}
"""


def vue_page_spec_doc_template(inline: bool) -> str:
    component_name = "PageSpecDocInline" if inline else "PageSpecDoc"
    props_block = 'const props = defineProps<{ pageKey: PageSpecKey }>();' if inline else 'const props = defineProps<{ pageKey: PageSpecKey }>();\nconst emit = defineEmits<{ back: [] }>();'
    retry_or_back = "" if inline else '      <button type="button" @click="emit(\'back\')">返回产品页</button>\n'
    margin_class = " proto-spec-doc--inline" if inline else ""
    return f"""<script setup lang="ts">
import {{ computed }} from "vue";

import {{ usePageSpec }} from "../page-specs/usePageSpec";
import type {{ PageSpecKey }} from "../page-specs/registry";

{props_block}
const pageKey = computed(() => props.pageKey);
const {{ spec, loading, error, reload }} = usePageSpec(() => pageKey.value);
</script>

<template>
  <section v-if="loading" class="proto-spec-doc{margin_class}" data-role="page-spec">
    加载需求说明...
  </section>

  <section v-else-if="error" class="proto-spec-doc{margin_class}" data-role="page-spec">
    <header class="proto-spec-doc__header">
      <h2>需求说明加载失败</h2>
      <button type="button" @click="reload">重试</button>
    </header>
    <p>{{{{ error.message }}}}</p>
  </section>

  <section
    v-else-if="spec"
    class="proto-spec-doc{margin_class}"
    data-role="page-spec"
    data-spec-origin="prototype-spec-annotator"
    :data-spec-page="props.pageKey"
    :data-spec-id="`${{props.pageKey}}-spec`"
    :data-spec-batch="spec.meta.batchId"
    data-spec-visible="true"
  >
    <header class="proto-spec-doc__header">
      <div>
        <p class="proto-spec-doc__eyebrow">Requirement Spec</p>
        <h2>{{{{ spec.pageName }}}} 页面规则说明</h2>
        <p>{{{{ spec.summary }}}}</p>
      </div>
{retry_or_back}    </header>

    <section v-if="spec.secondarySurfaces?.length" class="proto-spec-doc__surface-list">
      <h3>二级承载面</h3>
      <ul>
        <li v-for="item in spec.secondarySurfaces" :key="item">{{{{ item }}}}</li>
      </ul>
    </section>

    <div class="proto-spec-doc__sections">
      <article v-for="section in spec.sections" :key="section.id" class="proto-spec-doc__section">
        <h3>{{{{ section.title }}}}</h3>
        <ol>
          <li v-for="(rule, index) in section.rules" :key="`${{section.id}}-${{index}}`">{{{{ rule }}}}</li>
        </ol>
        <table v-if="section.fields?.length" class="proto-spec-doc__fields">
          <thead>
            <tr>
              <th>字段</th>
              <th>说明</th>
              <th>必填</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="field in section.fields" :key="field.id">
              <td>{{{{ field.name }}}}</td>
              <td>{{{{ field.description ?? field.value ?? "待补充" }}}}</td>
              <td>{{{{ field.required ? "是" : "否" }}}}</td>
            </tr>
          </tbody>
        </table>
      </article>
    </div>
  </section>
</template>
"""


def vue_page_spec_shell_template() -> str:
    return """<script setup lang="ts">
import { ref } from "vue";

import type { PageSpecKey } from "../page-specs/registry";
import PageSpecDoc from "./PageSpecDoc.vue";

const props = defineProps<{ pageKey: PageSpecKey }>();
const mode = ref<"page" | "spec">("page");
</script>

<template>
  <div class="proto-spec-shell" :data-page-spec-key="props.pageKey">
    <header class="proto-spec-shell__toolbar">
      <div class="proto-spec-shell__switcher">
        <button type="button" :aria-pressed="mode === 'page'" @click="mode = 'page'">
          产品页面
        </button>
        <button type="button" :aria-pressed="mode === 'spec'" @click="mode = 'spec'">
          需求说明
        </button>
      </div>
    </header>
    <div class="proto-spec-shell__body">
      <slot v-if="mode === 'page'" />
      <PageSpecDoc v-else :page-key="props.pageKey" @back="mode = 'page'" />
    </div>
  </div>
</template>
"""


def vue_fixed_shell_example_template(component_name: str, page_key: str) -> str:
    return f"""<script setup lang="ts">
import PageSpecShell from "../../components/PageSpecShell.vue";
import {{ PAGE_SPEC_KEYS }} from "../registry";
</script>

<template>
  <PageSpecShell :page-key="PAGE_SPEC_KEYS.{to_camel_case(page_key)}">
    <section class="proto-page-stage">
      <h1>{component_name}</h1>
      <p>TODO: replace this example body with the real page content.</p>
    </section>
  </PageSpecShell>
</template>
"""


def vue_document_flow_example_template(component_name: str, page_key: str) -> str:
    return f"""<script setup lang="ts">
import PageSpecDocInline from "../../components/PageSpecDocInline.vue";
import {{ PAGE_SPEC_KEYS }} from "../registry";
</script>

<template>
  <main class="proto-page-stage">
    <section>
      <h1>{component_name}</h1>
      <p>TODO: replace this example body with the real page content.</p>
    </section>
    <PageSpecDocInline :page-key="PAGE_SPEC_KEYS.{to_camel_case(page_key)}" />
  </main>
</template>
"""


def html_render_script_template() -> str:
    return """(function (global) {
  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function renderFields(fields) {
    if (!Array.isArray(fields) || !fields.length) {
      return "";
    }

    return `
      <table class="proto-spec-doc__fields">
        <thead>
          <tr>
            <th>字段</th>
            <th>说明</th>
            <th>必填</th>
          </tr>
        </thead>
        <tbody>
          ${fields
            .map((field) => `
              <tr>
                <td>${escapeHtml(field.name)}</td>
                <td>${escapeHtml(field.description || field.value || "待补充")}</td>
                <td>${field.required ? "是" : "否"}</td>
              </tr>
            `)
            .join("")}
        </tbody>
      </table>
    `;
  }

  function renderPageSpecDoc(spec, root, options) {
    if (!spec || !root) {
      return;
    }

    const pageKey = options && options.pageKey ? options.pageKey : spec.pageKey;
    const batchId = spec.meta && spec.meta.batchId ? spec.meta.batchId : "spec-batch-scaffold";
    const sections = Array.isArray(spec.sections) ? spec.sections : [];
    const surfaces = Array.isArray(spec.secondarySurfaces) ? spec.secondarySurfaces : [];

    root.setAttribute("data-role", "page-spec");
    root.setAttribute("data-spec-origin", "prototype-spec-annotator");
    root.setAttribute("data-spec-page", pageKey);
    root.setAttribute("data-spec-id", `${pageKey}-spec`);
    root.setAttribute("data-spec-batch", batchId);
    root.setAttribute("data-spec-visible", "true");

    root.innerHTML = `
      <header class="proto-spec-doc__header">
        <div>
          <p class="proto-spec-doc__eyebrow">Requirement Spec</p>
          <h2>${escapeHtml(spec.pageName)} 页面规则说明</h2>
          <p>${escapeHtml(spec.summary)}</p>
        </div>
      </header>
      ${
        surfaces.length
          ? `
            <section class="proto-spec-doc__surface-list">
              <h3>二级承载面</h3>
              <ul>${surfaces.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
            </section>
          `
          : ""
      }
      <div class="proto-spec-doc__sections">
        ${sections
          .map((section) => `
            <article class="proto-spec-doc__section">
              <h3>${escapeHtml(section.title)}</h3>
              <ol>
                ${(section.rules || []).map((rule) => `<li>${escapeHtml(rule)}</li>`).join("")}
              </ol>
              ${renderFields(section.fields)}
            </article>
          `)
          .join("")}
      </div>
    `;
  }

  global.renderPageSpecDoc = renderPageSpecDoc;
})(window);
"""


def html_inline_script_template() -> str:
    return """(function () {
  async function loadSpec(pageKey) {
    const response = await fetch(`./prototype-specs/current/${pageKey}.json`);
    if (!response.ok) {
      throw new Error(`Failed to load page spec: ${response.status}`);
    }
    return response.json();
  }

  async function bootstrap() {
    const pageKey = document.body.dataset.pageSpecKey;
    const root = document.getElementById("proto-spec-root");
    if (!pageKey || !root || typeof window.renderPageSpecDoc !== "function") {
      return;
    }

    try {
      const spec = await loadSpec(pageKey);
      window.renderPageSpecDoc(spec, root, { pageKey });
    } catch (error) {
      root.textContent = error instanceof Error ? error.message : "Failed to load page spec.";
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    void bootstrap();
  });
})();
"""


def html_shell_script_template() -> str:
    return """(function () {
  async function loadSpec(pageKey) {
    const response = await fetch(`./prototype-specs/current/${pageKey}.json`);
    if (!response.ok) {
      throw new Error(`Failed to load page spec: ${response.status}`);
    }
    return response.json();
  }

  function wireViewToggle() {
    const pageView = document.getElementById("proto-page-view");
    const specView = document.getElementById("proto-spec-view");
    const buttons = document.querySelectorAll("[data-target-view]");

    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        const target = button.dataset.targetView;
        if (!pageView || !specView) {
          return;
        }
        pageView.hidden = target !== "page";
        specView.hidden = target !== "spec";
      });
    });
  }

  async function bootstrap() {
    const pageKey = document.body.dataset.pageSpecKey;
    const specView = document.getElementById("proto-spec-view");
    if (!pageKey || !specView || typeof window.renderPageSpecDoc !== "function") {
      return;
    }

    try {
      const spec = await loadSpec(pageKey);
      window.renderPageSpecDoc(spec, specView, { pageKey });
    } catch (error) {
      specView.textContent = error instanceof Error ? error.message : "Failed to load page spec.";
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    wireViewToggle();
    void bootstrap();
  });
})();
"""


def html_style_block() -> str:
    return """<style>
  :root {
    color-scheme: light;
    font-family: "SF Pro Text", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
    background: #f5f7fb;
    color: #172033;
  }

  body {
    margin: 0;
    background: #f5f7fb;
  }

  .proto-page-shell,
  .proto-page-stage,
  .proto-spec-doc {
    box-sizing: border-box;
  }

  .proto-page-shell {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  .proto-spec-switcher {
    display: flex;
    gap: 8px;
    padding: 16px 20px;
    border-bottom: 1px solid #d8dfeb;
    background: #ffffff;
  }

  .proto-spec-switcher button {
    border: 1px solid #c7d2e4;
    border-radius: 999px;
    background: #ffffff;
    padding: 8px 14px;
    cursor: pointer;
  }

  .proto-page-stage,
  .proto-page-view {
    padding: 24px;
  }

  .proto-spec-doc {
    margin: 24px;
    border: 1px solid #d8dfeb;
    border-radius: 20px;
    background: #ffffff;
    padding: 24px;
  }

  .proto-spec-doc__header {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: flex-start;
    margin-bottom: 20px;
  }

  .proto-spec-doc__eyebrow {
    margin: 0 0 8px;
    color: #5a6b8c;
    font-size: 12px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .proto-spec-doc__surface-list,
  .proto-spec-doc__section {
    border-top: 1px solid #e7edf7;
    padding-top: 16px;
    margin-top: 16px;
  }

  .proto-spec-doc__fields {
    width: 100%;
    border-collapse: collapse;
    margin-top: 12px;
  }

  .proto-spec-doc__fields th,
  .proto-spec-doc__fields td {
    border: 1px solid #d8dfeb;
    padding: 8px 10px;
    text-align: left;
  }
</style>"""


def html_fixed_shell_example_template(page_key: str, page_name: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{page_name} Spec Shell Example</title>
    {html_style_block()}
  </head>
  <body data-page-spec-key="{page_key}">
    <div class="proto-page-shell">
      <div class="proto-spec-switcher">
        <button type="button" data-target-view="page">产品页面</button>
        <button type="button" data-target-view="spec">需求说明</button>
      </div>

      <main id="proto-page-view" class="proto-page-view">
        <section class="proto-page-stage">
          <h1>{page_name}</h1>
          <p>TODO: replace this example body with the real page content.</p>
        </section>
      </main>

      <section id="proto-spec-view" class="proto-spec-doc" hidden></section>
    </div>

    <script src="assets/page-spec-render.js"></script>
    <script src="assets/page-spec-shell.js"></script>
  </body>
</html>
"""


def html_document_flow_example_template(page_key: str, page_name: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{page_name} Inline Spec Example</title>
    {html_style_block()}
  </head>
  <body data-page-spec-key="{page_key}">
    <main class="proto-page-stage">
      <section>
        <h1>{page_name}</h1>
        <p>TODO: replace this example body with the real page content.</p>
      </section>
    </main>

    <section id="proto-spec-root" class="proto-spec-doc"></section>

    <script src="assets/page-spec-render.js"></script>
    <script src="assets/page-spec-inline.js"></script>
  </body>
</html>
"""


def scaffold_react(
    root: Path,
    layout: str,
    page_key: str,
    route_path: str,
    component_name: str,
    force: bool,
) -> list[WriteResult]:
    src_dir = root / "src"
    page_specs_dir = src_dir / "page-specs"
    components_dir = src_dir / "components"
    examples_dir = page_specs_dir / "examples"
    results: list[WriteResult] = []

    results.append(write_text(page_specs_dir / "schema.ts", react_or_vue_schema_template(), force))
    results.append(write_text(page_specs_dir / "index.ts", react_or_vue_index_template(), force))
    results.append(write_text(page_specs_dir / "usePageSpec.ts", react_use_page_spec_template(), force))
    results.append(ensure_marker_block(page_specs_dir / "registry.ts", REGISTRY_KEYS_MARKER, f'  {to_camel_case(page_key)}: "{page_key}",', force))
    results.append(ensure_marker_block(page_specs_dir / "registry.ts", REGISTRY_ROUTES_MARKER, f'  "{route_path}": PAGE_SPEC_KEYS.{to_camel_case(page_key)},', force))
    results.append(ensure_history_slot(page_specs_dir, page_key))

    if layout == "fixed-shell":
        results.append(write_text(components_dir / "PageSpecDoc.tsx", react_page_spec_doc_template(inline=False), force))
        results.append(write_text(components_dir / "withPageSpec.tsx", react_with_page_spec_template(), force))
        results.append(
            write_text(
                examples_dir / f"{component_name}.integration.example.tsx",
                react_fixed_shell_example_template(component_name, page_key),
                force,
            )
        )
    else:
        results.append(write_text(components_dir / "PageSpecDocInline.tsx", react_page_spec_doc_template(inline=True), force))
        results.append(
            write_text(
                examples_dir / f"{component_name}.integration.example.tsx",
                react_document_flow_example_template(component_name, page_key),
                force,
            )
        )

    return results


def scaffold_vue(
    root: Path,
    layout: str,
    page_key: str,
    route_path: str,
    component_name: str,
    force: bool,
) -> list[WriteResult]:
    src_dir = root / "src"
    page_specs_dir = src_dir / "page-specs"
    components_dir = src_dir / "components"
    examples_dir = page_specs_dir / "examples"
    results: list[WriteResult] = []

    results.append(write_text(page_specs_dir / "schema.ts", react_or_vue_schema_template(), force))
    results.append(write_text(page_specs_dir / "index.ts", react_or_vue_index_template(), force))
    results.append(write_text(page_specs_dir / "usePageSpec.ts", vue_use_page_spec_template(), force))
    results.append(ensure_marker_block(page_specs_dir / "registry.ts", REGISTRY_KEYS_MARKER, f'  {to_camel_case(page_key)}: "{page_key}",', force))
    results.append(ensure_marker_block(page_specs_dir / "registry.ts", REGISTRY_ROUTES_MARKER, f'  "{route_path}": PAGE_SPEC_KEYS.{to_camel_case(page_key)},', force))
    results.append(ensure_history_slot(page_specs_dir, page_key))

    if layout == "fixed-shell":
        results.append(write_text(components_dir / "PageSpecDoc.vue", vue_page_spec_doc_template(inline=False), force))
        results.append(write_text(components_dir / "PageSpecShell.vue", vue_page_spec_shell_template(), force))
        results.append(
            write_text(
                examples_dir / f"{component_name}.integration.example.vue",
                vue_fixed_shell_example_template(component_name, page_key),
                force,
            )
        )
    else:
        results.append(write_text(components_dir / "PageSpecDocInline.vue", vue_page_spec_doc_template(inline=True), force))
        results.append(
            write_text(
                examples_dir / f"{component_name}.integration.example.vue",
                vue_document_flow_example_template(component_name, page_key),
                force,
            )
        )

    return results


def scaffold_html(
    root: Path,
    layout: str,
    page_key: str,
    page_name: str,
    html_file: str,
    force: bool,
) -> list[WriteResult]:
    results: list[WriteResult] = []
    assets_dir = root / "assets"

    results.append(ensure_history_slot(detect_spec_dir(root), page_key))
    results.append(write_text(assets_dir / "page-spec-render.js", html_render_script_template(), force))

    if layout == "fixed-shell":
        results.append(write_text(assets_dir / "page-spec-shell.js", html_shell_script_template(), force))
        results.append(write_text(root / html_file, html_fixed_shell_example_template(page_key, page_name), force))
    else:
        results.append(write_text(assets_dir / "page-spec-inline.js", html_inline_script_template(), force))
        results.append(write_text(root / html_file, html_document_flow_example_template(page_key, page_name), force))

    return results


def print_results(results: list[WriteResult]) -> None:
    for result in results:
        print(f"{result.status:>9}  {result.path}")


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    page_key = args.page_key.strip()
    page_name = args.page_name.strip() if args.page_name else default_page_name(page_key)
    route_path = args.route_path.strip() if args.route_path else f"/{page_key}"

    if args.framework in {"react", "vue"}:
        ensure_directory(root / "src")

    source_scripts = Path(__file__).resolve().parent
    init_project(
        target_root=root,
        source_scripts=source_scripts,
        copy_scripts=True,
        seed_pages=[{"pageKey": page_key, "pageName": page_name, "sourceFile": "", "routeHint": route_path}],
        legacy_json=True,
    )

    if args.framework == "react":
        component_name = args.component_name or f"{to_pascal_case(page_key)}Page"
        results = scaffold_react(
            root=root,
            layout=args.layout,
            page_key=page_key,
            route_path=route_path,
            component_name=component_name,
            force=args.force,
        )
    elif args.framework == "vue":
        component_name = args.component_name or f"{to_pascal_case(page_key)}View"
        results = scaffold_vue(
            root=root,
            layout=args.layout,
            page_key=page_key,
            route_path=route_path,
            component_name=component_name,
            force=args.force,
        )
    else:
        suffix = "fixed-shell" if args.layout == "fixed-shell" else "inline"
        html_file = args.html_file or f"{page_key}.page-spec.{suffix}.example.html"
        results = scaffold_html(
            root=root,
            layout=args.layout,
            page_key=page_key,
            page_name=page_name,
            html_file=html_file,
            force=args.force,
        )

    print("\nGenerated scaffold files:")
    print_results(results)
    print("\nNext step: move the integration example into the real business page or route and wire the generated loader/components into the target project.")


if __name__ == "__main__":
    main()
