# Skeleton: Vue Document Flow Inline

> Legacy skeleton: new work should keep `current/<pageKey>.md` as source of truth. Use this only for old inline/static Vue delivery or migration support.

适用场景：

- Vue 项目
- 页面内容本身在正常文档流中
- 说明区应作为文档层直接接在页面末尾

## 1. 默认目录

```text
src/
  page-specs/
    current/
      resource-detail.json
    index.ts
  components/
    PageSpecDocInline.vue
  views/
    ResourceDetailView.vue
```

如果需要长期维护，再补 `history/`、`schema.ts` 和保存链路。

## 2. 页面挂载

```vue
<template>
  <main class="mx-auto max-w-6xl px-6 py-8">
    <ResourceDetailContent />
    <PageSpecDocInline page-key="resource-detail" />
  </main>
</template>
```

说明区必须是页面尾部独立 sibling，不要塞进业务卡片、Tab、Drawer。

## 3. 稳定 pageKey

```ts
export const PAGE_SPEC_KEYS = {
  resourceDetail: "resource-detail",
} as const;
```

禁止从 `route.path` 或展示文本派生。

## 4. inline 说明组件

```vue
<script setup lang="ts">
const props = defineProps<{ pageKey: "resource-detail" }>();
const { spec, loading, error } = usePageSpec(props.pageKey);
</script>

<template>
  <section v-if="!loading && spec && !error" class="proto-spec-doc mt-10 border-t border-dashed border-slate-300 pt-6" data-role="page-spec">
    <div class="proto-spec-divider rounded-3xl border border-slate-200 bg-slate-50 p-6">
      <h2 class="text-xl font-semibold">{{ spec.pageName }} 页面规则说明</h2>
    </div>
  </section>
</template>
```

## 5. 如果项目要求可编辑

- 继续用 `current/history`
- 保存后写回项目文件/API
- inline 只是展示模式，不代表可以跳过结构化编辑

## 6. 直接失败

- 主说明放进 `Dialog` / `Drawer`
- 页面底部只留一个“查看完整说明”按钮
- `pageKey` 依赖 `route.path.replace(...)`

## 7. 收尾检查

- validator 通过
- 构建命令通过
