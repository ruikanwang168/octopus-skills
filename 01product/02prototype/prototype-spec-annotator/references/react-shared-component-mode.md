# React Shared Component Mode

> Markdown-first update: this file is legacy guidance for older `pageSpecs.ts` / `withPageSpec` implementations. For new work, keep `current/<pageKey>.md` as the source of truth and read `references/framework-integration.md` first. Use `withPageSpec` only as a display shell, not as the data source.

## Contents

- 0. 先记住这些硬失败
- 1. 推荐架构
- 1.5 不要发明新的捷径架构
- 2. 默认承载模式
- 3. PageSpecDoc 标准实现
- 3.5 结构化编辑要求
- 4. withPageSpec 标准实现
- 4.5 稳定 pageKey 映射
- 4. pageSpecs 数据建议
- 5. 默认策略
- 6. 什么时候用组件级显隐，什么时候用脚本级显隐
- 7. 注意事项

当目标项目不是把说明区直接写进单页文件，而是采用共享 `PageSpecDoc` / `withPageSpec` / `pageSpecs` 模式时，按这个文件执行。

适用场景：

- React / Vite / Next 项目
- 多个页面统一通过高阶组件或布局组件挂载说明区
- 用户希望所有说明默认支持唯一标记、批次标记和运行时显隐

如果项目同时满足以下任一条件：

- 路由数明显大于 1
- 有 `pages/`、`routes/`、`layouts/`
- 用户要求全量生成全部页面说明
- 用户要求后续还能手动编辑、单页重生成、覆盖确认

则本文件不能单独使用，必须和 `cross-framework-spec-storage-mode.md` 一起执行。
原因是这时目标已经不是“共享展示组件”，而是“共享展示组件 + 可持续维护的数据层”。

## 0. 先记住这些硬失败

命中 React 共享组件模式后，以下结果直接视为失败，不要交付：

- 在 `Layout` / `Outlet` 文件里直接渲染 `<PageSpecDoc />`
- 真实页面继续同屏渲染，主说明却藏在 `Drawer` / `Sheet` / `Dialog` / `Popover`
- `pageKey` 通过 `pathname.replace(...)`、导航文案、标题文本、`label.toLowerCase()` 等临时推导得到
- 只有 `PageSpecDoc.tsx` 和一批 JSON，但真实业务页没有通过 `withPageSpec` 或等价壳层接入
- 声称“支持编辑”，实际只把 `rules.join('\n')` 塞进一个大文本框，或只写进 `localStorage`

## 1. 推荐架构

推荐拆成三层：

1. `current/<pageKey>.md`：说明数据源；必要时再生成 `pageSpecs.ts` / manifest 作为运行时适配层
2. `PageSpecDoc.tsx`：只负责说明区的展示、标记和显隐
3. `withPageSpec.tsx`：负责把原页面和说明区组合起来

如果项目属于“多页面 + 持续维护”场景，还要同时具备：

4. `current/<pageKey>.md` 当前说明文件
5. `history/<pageKey>/*` 快照目录
6. 稳定 `pageKey` 注册表或等价显式映射

优点：

- 所有页面共享同一套显隐逻辑
- 所有说明天然带统一标记协议
- 后续既可以代码内显隐，也可以脚本级 `clear` / `toggle`

但要注意：

- 仅有 `pageSpecs.ts + PageSpecDoc.tsx + withPageSpec.tsx`，并不自动等于“可编辑”
- 如果用户需要后续维护，必须再补当前说明文件层、保存链路和覆盖确认链路
- 如果用户需要结构化编辑，`PageSpecDoc.tsx` 不能只给一个大 textarea 让用户自己用换行维护 `rules[]`；默认要保留逐条规则的新增、删除和单项修改

## 1.5 不要发明新的捷径架构

默认先套用这套模板，不要临场自由拼：

- `current/*.md`、由 Markdown 派生的 manifest、或等价当前说明源
- `PageSpecDoc.tsx`
- `withPageSpec.tsx`
- 稳定 `pageKey` 注册表
- 页面级包装接线

除非用户明确要求其他结构，且你能证明新的结构仍然满足：

- 主说明不被覆盖层隐藏
- 真实业务页已经接入
- `pageKey` 稳定且与说明文件名一致
- 后续可编辑、可重生成、可覆盖确认

## 2. 默认承载模式

如果目标项目是普通文档流页面，可以使用“页面在上、说明在下”的堆叠模式。

如果目标项目是后台工作台，并且存在这些信号：

- `h-screen` / `min-h-0` / `overflow-hidden`
- 页面组件自己就是 `flex-1 overflow-y-auto`
- 多列或多面板各自独立滚动

默认不要再使用堆叠模式。应改为：

- `withPageSpec` 提供 `page | spec` 两个视图
- 用户在“产品页面”和“需求说明”之间切换
- 任一时刻只显示一个视图
- 主说明直接在 `spec` 视图中完整展示，而不是再套一个“查看完整说明”按钮把内容放进抽屉

这样可以彻底避免双滚动上下文下的视觉重叠。

## 3. PageSpecDoc 标准实现

推荐最小接口：

```tsx
import React from "react";
import type { PageSpec } from "@/data/pageSpecs";

interface PageSpecDocProps {
  spec: PageSpec;
  pageId: string;
  onBackToPage?: () => void;
}

export const PageSpecDoc = ({
  spec,
  pageId,
  onBackToPage,
}: PageSpecDocProps) => {
  return (
    <section
      className="proto-spec-doc h-full overflow-y-auto bg-slate-50/90 px-6 py-6 text-slate-900"
      data-role="page-spec"
      data-spec-origin="prototype-spec-annotator"
      data-spec-page={pageId}
      data-spec-id={`${pageId}-spec`}
      data-spec-batch="spec-batch-20260421-153000"
      data-spec-visible="true"
    >
      <div className="proto-spec-divider mx-auto max-w-6xl rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <span className="proto-spec-eyebrow inline-flex rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600">
              需求说明
            </span>
            <h2 className="mt-4 text-2xl font-semibold tracking-tight text-slate-900">
              {spec.pageName} 页面规则说明
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              当前为需求说明视图，说明内容与原型操作界面分开展示。
            </p>
          </div>
          {onBackToPage && (
            <button
              type="button"
              className="proto-spec-toggle rounded-full border border-slate-200 bg-white px-4 py-2 text-xs text-slate-600"
              onClick={onBackToPage}
            >
              返回页面内容
            </button>
          )}
        </div>
      </div>

      <div className="proto-spec-panel mx-auto mt-6 grid max-w-6xl gap-4">
        {spec.sections.map((section) => (
          <article
            key={section.title}
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <h3 className="text-base font-semibold text-slate-900">{section.title}</h3>
            <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-6 text-slate-700">
              {section.rules.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ol>
          </article>
        ))}
      </div>
    </section>
  );
};
```

## 3.5 结构化编辑要求

如果项目进入“可编辑说明架构”，`PageSpecDoc` 的编辑态默认要满足以下要求：

- `summary` 可直接编辑
- `sections[].title` 可直接编辑
- `sections[]` 默认支持新增章节，必要时也支持删除章节
- `sections[].rules` 逐条渲染，而不是 `rules.join('\n')` 后塞进一个大文本框
- 每条规则至少支持：
  - 修改当前内容
  - 新增下一条规则
  - 删除当前规则
- 当某个章节只剩一条规则时，也要保留最小可编辑占位，而不是把整个章节直接改成空数组
- 如果章节存在 `fields[]`，字段表也应保持逐项编辑，并支持新增 / 删除字段，而不是把整张表压成一段原始 JSON

默认不推荐的退化实现：

- `value={section.rules.join('\n')}`
- `onChange => split('\n').filter(Boolean)`

这种实现虽然“勉强可改文字”，但会丢失结构化编辑体验，也容易让用户误删规则边界。除非用户明确要求“原始文本模式”，否则不要作为默认交付。

## 4. withPageSpec 标准实现

对工作台项目，推荐让 `withPageSpec` 负责视图切换，不再把说明区直接堆到页面下方：

```tsx
import { useEffect, useState, type ComponentType } from "react";
import { PageSpecDoc } from "@/components/PageSpecDoc";
import type { PageSpecKey } from "@/data/pageSpecs";

export const withPageSpec = <P extends object>(
  pageKey: PageSpecKey,
  Component: ComponentType<P>
) => {
  const WrappedComponent = (props: P) => {
    const storageKey = `proto-spec:${pageKey}:view`;
    const [mode, setMode] = useState<"page" | "spec">("page");

    useEffect(() => {
      const saved = window.localStorage.getItem(storageKey);
      if (saved === "page" || saved === "spec") setMode(saved);
    }, [storageKey]);

    useEffect(() => {
      window.localStorage.setItem(storageKey, mode);
    }, [storageKey, mode]);

    return (
      <div className="flex h-full min-h-0 flex-col bg-background">
        <div className="shrink-0 border-b border-border bg-card px-4 py-3">
          <div className="inline-flex rounded-xl border border-border bg-background p-1">
            <button type="button" onClick={() => setMode("page")}>
              产品页面
            </button>
            <button type="button" onClick={() => setMode("spec")}>
              需求说明
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1">
          {mode === "page" ? (
            <Component {...props} />
          ) : (
            <PageSpecDoc
              spec={pageSpecs[pageKey]}
              pageId={pageKey}
              onBackToPage={() => setMode("page")}
            />
          )}
        </div>
      </div>
    );
  };

  WrappedComponent.displayName = `withPageSpec(${Component.displayName || Component.name || pageKey})`;
  return WrappedComponent;
};
```

如果目标页面是普通文档流单页，没有内部滚动和固定工作台壳层，才可以退回到堆叠模式。

## 4.5 稳定 pageKey 映射

React 共享组件模式里，`pageKey` 不要从路由文本临时推导，默认要显式映射：

```ts
export const PAGE_SPEC_ROUTE_MAP = {
  "/": "home",
  "/market": "market",
  "/kb-square": "kb-square",
  "/agents": "agent-square",
  "/admin": "admin-dashboard",
  "/admin/users": "admin-users",
} as const;

export type PageSpecKey = (typeof PAGE_SPEC_ROUTE_MAP)[keyof typeof PAGE_SPEC_ROUTE_MAP];

export function resolvePageSpecKey(pathname: string): PageSpecKey | null {
  return PAGE_SPEC_ROUTE_MAP[pathname as keyof typeof PAGE_SPEC_ROUTE_MAP] ?? null;
}
```

明确禁止：

- `pathname.replace(/^\//, '').replace(/\//g, '-')`
- `current?.label?.toLowerCase().replace(/\s+/g, '-')`
- 从标题、副标题、导航展示名称直接拼说明 key

## 4. pageSpecs 数据建议

`pageSpecs.ts` 里只保留纯数据，不混显隐逻辑：

```ts
export interface PageSpec {
  pageName: string;
  pageType: "列表页" | "详情页" | "表单页" | "工具页";
  pageShape: "桌面端页面" | "移动端页面" | "大屏页面" | "AIGC 页面";
  summary: string;
  secondarySurfaces?: string[];
  sections: Array<{
    title: string;
    rules: string[];
  }>;
}

export const pageSpecs = {
  AskData: {
    pageName: "智能问数",
    pageType: "工具页",
    pageShape: "AIGC 页面",
    summary: "该页面用于以自然语言查询数据库。",
    sections: [],
  },
} as const;
```

## 5. 默认策略

React 共享组件模式下，默认这样处理：

- 默认给所有说明共享同一个 `batch-id`
- 默认每页 `spec-id = {pageKey}-spec`
- 默认 `defaultVisible = true`
- 如果用户明确要求默认收起，则设置 `defaultVisible = false`
- 如果用户明确要求用户自己控制，则保持 `collapsible = true`

如果是多页面 React 持续维护场景，再额外强制：

- 真实业务页必须接入 `withPageSpec`
- 不能只把 `PageSpecDoc` 放到 demo 页面里
- 不能继续在页面组件底部堆静态 `proto-spec-doc`
- 必须结合 `current/history` 或等价持久层，确保说明不是一次性文案
- 不能把主说明视图退化成 `PageSpecDoc` 内部的 `Sheet` / `Drawer`

## 6. 什么时候用组件级显隐，什么时候用脚本级显隐

优先级建议：

- 组件级显隐：适合 React / Vue 共享组件项目，用户需要在页面运行时自己开关
- 脚本级显隐：适合纯 HTML / JSX inline 插入场景，或需要批量切换源码默认状态
- 脚本级删除：适合用户确认要彻底清掉说明

## 7. 注意事项

- `PageSpecDoc` 根节点必须保留 `data-spec-*` 属性，不能只在外层包裹组件上打标
- 折叠按钮应放在标题区，不要混进业务操作栏
- `hidden` 与 `data-spec-visible` 必须同步
- 如果要让用户在运行时自己展开，优先让说明区壳层常驻，只折叠正文面板
- 如果使用 `localStorage` 记住用户选择，键名应包含页面标识，避免多页串扰
- 多页面项目里，`withPageSpec` 的真实接入优先级高于演示页；如果业务页仍然保留静态说明块，说明落地不合格
