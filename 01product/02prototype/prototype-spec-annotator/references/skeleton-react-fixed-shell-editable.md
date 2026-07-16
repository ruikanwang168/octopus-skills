# Skeleton: React Fixed Shell Editable

> Legacy skeleton: new work should keep `current/<pageKey>.md` as source of truth. Use this only for old JSON-based React delivery or migration support.

适用场景：

- React / Vite / Next 项目
- 页面存在 `h-screen`、`min-h-0`、`overflow-hidden`
- 后台工作台、运营台、管理台、门户壳层
- 需要后续手动编辑、单页重生成、覆盖确认

## 1. 默认目录

```text
src/
  page-specs/
    current/
      market.json
      admin-dashboard.json
    history/
      market/
      admin-dashboard/
    schema.ts
    registry.ts
    index.ts
  components/
    PageSpecDoc.tsx
    withPageSpec.tsx
  pages/
    MarketPage.tsx
    AdminDashboardPage.tsx
```

## 2. 必备结构

- `current/*.json`：当前生效说明
- `history/*`：覆盖或手动保存前的快照
- `registry.ts`：稳定 `pageKey` 与路由/页面的显式映射
- `index.ts`：统一加载/保存说明
- `PageSpecDoc.tsx`：完整说明视图，不开 `Sheet/Drawer`
- `withPageSpec.tsx`：产品页 / 需求说明 双视图壳层

## 3. 稳定 pageKey

```ts
export const PAGE_SPEC_ROUTE_MAP = {
  "/market": "market",
  "/admin": "admin-dashboard",
  "/admin/users": "admin-users",
} as const;

export type PageSpecKey = (typeof PAGE_SPEC_ROUTE_MAP)[keyof typeof PAGE_SPEC_ROUTE_MAP];
```

禁止：

- `location.pathname.replace(...)`
- `label.toLowerCase().replace(...)`
- 从标题文本临时拼 key

## 4. 说明数据入口

```ts
const bundledModules = import.meta.glob("./current/*.json", {
  eager: true,
  import: "default",
});

export async function loadPageSpec(pageKey: PageSpecKey) {
  try {
    const response = await fetch(`/api/page-specs/${pageKey}`);
    if (!response.ok) throw new Error(String(response.status));
    return await response.json();
  } catch {
    return bundledModules[`./current/${pageKey}.json`];
  }
}
```

## 5. 双视图壳层

切换器必须与默认生成 viewer 一致：顶部居中固定定位，支持在任意区域按住拖动；移动超过约 5px 才视为拖动，拖动后的 click 不切换视图，刷新后不保留坐标。

```tsx
export function withPageSpec<P extends object>(pageKey: PageSpecKey, Component: ComponentType<P>) {
  return function PageWithSpec(props: P) {
    const [mode, setMode] = useState<"page" | "spec">("page");

    return (
      <div className="flex h-screen min-h-0 flex-col bg-background">
        <header className="shrink-0 border-b border-border bg-card px-4 py-3">
          <div className="inline-flex rounded-xl border border-border bg-background p-1">
            <button type="button" onClick={() => setMode("page")}>产品页面</button>
            <button type="button" onClick={() => setMode("spec")}>需求说明</button>
          </div>
        </header>
        <div className="min-h-0 flex-1">
          {mode === "page" ? <Component {...props} /> : <PageSpecDoc pageKey={pageKey} onBackToPage={() => setMode("page")} />}
        </div>
      </div>
    );
  };
}
```

## 6. 页面接线

```tsx
function MarketPage() {
  return <MarketContent />;
}

export default withPageSpec("market", MarketPage);
```

不要在共享 `Layout` 里这样做：

```tsx
<Outlet />
<PageSpecDoc pageKey="market" />
```

## 7. 主说明视图

- `PageSpecDoc.tsx` 必须直接渲染完整规则内容
- 如果支持编辑，规则按项编辑，不要 `join('\n')`
- 保存后写回项目文件/API，不要只写 `localStorage`

## 8. 直接失败

- `PageSpecDoc` 内部再开 `Sheet` / `Drawer` 展示“完整需求说明”
- 页面和说明同屏堆叠
- `pageKey` 没有显式映射
- 页面没用 `withPageSpec` 包装

## 9. 收尾检查

- `python3 scripts/validate_editable_specs.py --root <project>`
- 项目构建命令，例如 `npm run build`
