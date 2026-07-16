# Skeleton: Vue Fixed Shell Editable

> Legacy skeleton: new work should keep `current/<pageKey>.md` as source of truth. Use this only for old JSON-based Vue delivery or migration support.

适用场景：

- Vue 3 / Vite 项目
- 存在 `router-view`、侧栏、顶栏、`h-screen` / `overflow-hidden`
- 需要“产品页面 / 需求说明”双视图
- 需要后续手动编辑、重生成、覆盖确认

## 1. 默认目录

```text
src/
  page-specs/
    current/
      market.json
    history/
      market/
    schema.ts
    registry.ts
    index.ts
  components/
    PageSpecDoc.vue
    PageSpecShell.vue
  views/
    MarketView.vue
```

## 2. 稳定 pageKey

推荐用显式路由 meta：

```ts
{
  path: "/market",
  component: () => import("@/views/MarketView.vue"),
  meta: { pageSpecKey: "market" },
}
```

或者显式注册表：

```ts
export const PAGE_SPEC_ROUTE_MAP = {
  "/market": "market",
} as const;
```

禁止：

- `route.path.replace(...)`
- `route.name?.toLowerCase()`
- 从导航标题拼 key

## 3. 双视图壳层

切换器必须与默认生成 viewer 一致：顶部居中固定定位，支持在任意区域按住拖动；移动超过约 5px 才视为拖动，拖动后的 click 不切换视图，刷新后不保留坐标。

```vue
<script setup lang="ts">
import { ref } from "vue";
import PageSpecDoc from "./PageSpecDoc.vue";

const props = defineProps<{ pageKey: "market" }>();
const mode = ref<"page" | "spec">("page");
</script>

<template>
  <div class="flex h-screen min-h-0 flex-col bg-background">
    <header class="shrink-0 border-b border-border bg-card px-4 py-3">
      <div class="inline-flex rounded-xl border border-border bg-background p-1">
        <button type="button" @click="mode = 'page'">产品页面</button>
        <button type="button" @click="mode = 'spec'">需求说明</button>
      </div>
    </header>
    <div class="min-h-0 flex-1">
      <slot v-if="mode === 'page'" />
      <PageSpecDoc v-else :page-key="pageKey" @back="mode = 'page'" />
    </div>
  </div>
</template>
```

## 4. 页面接线

```vue
<template>
  <PageSpecShell page-key="market">
    <MarketContent />
  </PageSpecShell>
</template>
```

不要在共享 layout 里：

```vue
<RouterView />
<PageSpecDoc page-key="market" />
```

## 5. 说明数据入口

```ts
const modules = import.meta.glob("./current/*.json", { eager: true, import: "default" });

export async function loadPageSpec(pageKey: string) {
  try {
    const response = await fetch(`/api/page-specs/${pageKey}`);
    if (!response.ok) throw new Error(String(response.status));
    return await response.json();
  } catch {
    return modules[`./current/${pageKey}.json`];
  }
}
```

## 6. 直接失败

- 主说明藏在 `Drawer` / `Dialog`
- `PageSpecDoc` 追加在 `RouterView` 后面同屏展示
- 没有显式 `pageSpecKey`

## 7. 收尾检查

- validator 通过
- 构建命令通过
