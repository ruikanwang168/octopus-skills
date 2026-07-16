# Skeleton: HTML Fixed Shell Editable Toggle

> Current skeleton for static HTML projects. Keep `current/<pageKey>.md` as source of truth and use `proto-spec-server.mjs` for local preview plus persistent save API.

适用场景：

- 纯 HTML / 原生 JS / jQuery / Axure 补壳项目
- 页面存在顶栏、侧栏、内部滚动面板
- 主说明不能与产品页同屏堆叠

## 1. 默认目录

```text
prototype-specs/
  current/
    admin-dashboard.md
  history/
    admin-dashboard/
proto-spec-server.mjs
admin-dashboard.html
```

如果用户只能通过 `file://` 直开页面，说明视图可以只读展示，但不要宣称可持久编辑或可生成历史快照。

## 2. 页面骨架

切换器必须与默认生成 viewer 一致：顶部居中固定定位，支持在任意区域按住拖动；移动超过约 5px 才视为拖动，拖动后的 click 不切换视图，刷新后不保留坐标。

```html
<body data-page-spec-key="admin-dashboard">
  <div class="proto-page-shell">
    <div class="proto-spec-switcher">
      <button type="button" data-target-view="page">产品页面</button>
      <button type="button" data-target-view="spec">需求说明</button>
    </div>

    <main id="proto-page-view">
      <!-- 现有后台页面 -->
    </main>

    <section
      id="proto-spec-view"
      class="proto-spec-doc"
      data-role="page-spec"
      data-spec-origin="prototype-spec-annotator"
      data-spec-page="admin-dashboard"
      hidden
    ></section>
  </div>

  <!-- runner 会注入统一切换器、Markdown viewer 和编辑保存逻辑 -->
</body>
```

## 3. 主说明加载

```js
const pageKey = document.body.dataset.pageSpecKey;
fetch(`/prototype-specs/current/${pageKey}.md`)
  .then((res) => res.text())
  .then((markdown) => renderSpec(markdown, document.getElementById("proto-spec-view")));
```

`pageKey` 必须直接写在 `data-page-spec-key`，不要从 URL 文本临时拼接。

## 4. 编辑保存

本地预览必须从项目根目录启动：

```bash
node proto-spec-server.mjs --port 8080
```

保存 API 固定为 `PUT /__prototype-specs/specs/<pageKey>`。保存前必须把旧 `current/<pageKey>.md` 写入 `history/<pageKey>/<timestamp>.before-manual-save.md`。

## 5. 视图切换

```js
const pageView = document.getElementById("proto-page-view");
const specView = document.getElementById("proto-spec-view");

document.querySelectorAll("[data-target-view]").forEach((button) => {
  button.addEventListener("click", () => {
    const target = button.dataset.targetView;
    pageView.hidden = target !== "page";
    specView.hidden = target !== "spec";
  });
});
```

## 6. 直接失败

- 用侧滑抽屉、悬浮面板、右侧浮层承载主说明
- 继续让产品页和说明页同屏堆叠
- `pageKey` 从 URL `replace(...)` 生成
- 页面通过 `file://` 直开，却声称编辑会写回项目文件

## 7. 收尾检查

- `current/*.md` 必须通过 `validate_editable_specs.py`
- 切换器、说明页和 `编辑 / Markdown / 预览 / 保存 / 取消` 按钮样式应与 React / Vue 生成 viewer 使用同一套 `.proto-spec-*` 类名；切换器支持同一套拖动阈值和点击拦截；预览只渲染当前草稿，保存才写回 Markdown
- 页面切到 spec 视图后能看到完整规则
- 如果项目有构建/打包命令，也要跑通过
