# Skeleton: HTML Document Flow Inline

> Legacy skeleton: new work should keep `current/<pageKey>.md` as source of truth. Use this only for old inline/static HTML delivery or migration support.

适用场景：

- 纯 HTML 页面
- 页面内容在正常文档流里自然向下撑开
- 目标是把说明区作为独立文档层接在页面结尾

## 1. 默认目录

```text
prototype-specs/
  current/
    quality-object-config.json
assets/
  page-spec-inline.js
quality-object-config.html
```

## 2. 页面骨架

```html
<body data-page-spec-key="quality-object-config">
  <main class="prototype-page">
    <!-- 现有页面内容 -->
  </main>

  <section
    id="proto-spec-root"
    class="proto-spec-doc"
    data-role="page-spec"
    data-spec-origin="prototype-spec-annotator"
    data-spec-page="quality-object-config"
  ></section>

  <script src="assets/page-spec-inline.js"></script>
</body>
```

## 3. inline 渲染

```js
const pageKey = document.body.dataset.pageSpecKey;
const root = document.getElementById("proto-spec-root");

fetch(`./prototype-specs/current/${pageKey}.json`)
  .then((res) => res.json())
  .then((spec) => {
    root.innerHTML = `
      <div class="proto-spec-divider">
        <h2>${spec.pageName} 页面规则说明</h2>
      </div>
    `;
  });
```

## 4. 适用边界

- 适合单页、文档流页面、一次性交付
- 如果后续还要持续编辑，可继续保留 `current/history`，但挂载方式仍然是 inline
- 如果没有项目文件 API，不要误报成“支持多人共享编辑”

## 5. 直接失败

- 说明区插进业务卡片内部
- 为了看完整说明又额外开抽屉/弹窗
- `pageKey` 通过 URL 文本或标题文本临时拼出来

## 6. 收尾检查

- 说明区在页面尾部完整可见
- 不遮挡原页面
- `current/*.json` 可解析
