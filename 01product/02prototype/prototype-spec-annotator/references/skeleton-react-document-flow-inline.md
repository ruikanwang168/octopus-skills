# Skeleton: React Document Flow Inline

> Legacy skeleton: new work should keep `current/<pageKey>.md` as source of truth. Use this only for old inline/static React delivery or migration support.

适用场景：

- React 项目
- 页面主体在正常文档流中自然撑开
- 页面底部追加说明不会被裁切
- 单页交付，或多页面但当前目标页适合 inline 文档层

## 1. 默认目录

最小只读版：

```text
src/
  page-specs/
    current/
      resource-detail.json
    index.ts
  components/
    PageSpecDocInline.tsx
  pages/
    ResourceDetailPage.tsx
```

如果用户要求后续持续维护，再补：

```text
src/page-specs/history/*
src/page-specs/schema.ts
```

## 2. 挂载方式

说明区必须作为页面主内容结束后的独立 sibling。

```tsx
export default function ResourceDetailPage() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <ResourceDetailContent />
      <PageSpecDocInline pageKey="resource-detail" />
    </main>
  );
}
```

不要把说明区塞进：

- 现有业务卡片
- Tab 面板
- Form 区块
- Drawer / Dialog / Popover

## 3. 稳定 pageKey

```ts
export const PAGE_SPEC_KEYS = {
  resourceDetail: "resource-detail",
} as const;
```

仍然禁止从 `pathname.replace(...)`、标题文案、标签名称动态推导。

## 4. 说明组件

```tsx
export function PageSpecDocInline({ pageKey }: { pageKey: "resource-detail" }) {
  const { spec, loading, error } = usePageSpec(pageKey);

  if (loading) return <section className="proto-spec-doc">加载需求说明...</section>;
  if (error || !spec) return null;

  return (
    <section className="proto-spec-doc mt-10 border-t border-dashed border-slate-300 pt-6" data-role="page-spec">
      <div className="proto-spec-divider rounded-3xl border border-slate-200 bg-slate-50 p-6">
        <h2 className="text-xl font-semibold">{spec.pageName} 页面规则说明</h2>
      </div>
      <div className="proto-spec-panel mt-6 grid gap-4">
        {spec.sections.map((section) => (
          <article key={section.title} className="rounded-2xl border border-slate-200 bg-white p-5">
            <h3 className="font-semibold">{section.title}</h3>
          </article>
        ))}
      </div>
    </section>
  );
}
```

## 5. 如果项目要求可编辑

- 保留 `current/history` 目录
- `usePageSpec` 真实读取 `current/*.json` 或 API
- 编辑保存后写回项目文件/API
- inline 只是挂载方式，不代表可以退化成静态字符串

## 6. 直接失败

- 说明区只剩一个“查看完整说明”按钮
- 用 overlay 承载主说明
- 说明区嵌入业务模块内部，读者分不清它是文档层还是功能区

## 7. 收尾检查

- validator 必须通过
- 构建命令必须通过
