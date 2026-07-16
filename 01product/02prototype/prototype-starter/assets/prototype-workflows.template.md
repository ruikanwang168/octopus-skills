# 原型生成工作流

本文件承载低频教程和完整示例。日常执行先遵守根 `AGENTS.md` 和 `design-system/context-index.json`。

## 初始化与布局证据

初始化前运行 `validate_design_readiness.py`。退出码 2 时不得创建项目；先向用户确认，更新原始 DESIGN 和 `evidence.decisions`，再重新校验。

代表页面只来自 `pageTemplates[].representative: true`，并显式绑定一个 `layoutProfile`。每页只有一个产品根节点；区域和视口完全来自 profile。开发入口位于 `design-system/preview/index.html`，不能把切换器插入产品页。

```bash
node scripts/prepare-layout-audit.cjs
python3 -m http.server 8000
# 在浏览器打开 /design-system/layout-audit.html，导出 layout-report.json
node scripts/finalize-design-system.cjs --manifest design-system/preview-manifest.json
```

prepare 后任何代表页、shared、布局契约或 manifest 变化都会使布局报告失效；截图必须匹配 manifest 的精确视口且不能是纯色占位图。

## 普通新功能

```json
{
  "mode": "new-feature",
  "featureSlug": "02-user-management",
  "featureName": "用户管理",
  "updatedAt": "2026-07-13",
  "iterationName": "V2",
  "pages": [
    {
      "title": "用户列表",
      "path": "user-list",
      "pageKey": "user-list",
      "requirementStatus": "confirmed",
      "description": "新增组织筛选、组织字段和对应空状态。"
    }
  ]
}
```

脚本生成的 confirmed 页面只是 `scaffold`。完成真实业务实现后把 `data-generation-mode` 改为 `authored`。

## 现有功能微调

增量模式的核心不是“参考旧页面”，而是把旧页面作为不可丢失的基线复制，再做最小补丁。

```json
{
  "mode": "incremental",
  "featureSlug": "03-user-list-org-field",
  "featureName": "用户列表微调",
  "updatedAt": "2026-07-13",
  "iterationName": "V2.1",
  "pages": [
    {
      "title": "用户列表",
      "path": "user-list",
      "pageKey": "user-list-org-field",
      "requirementStatus": "confirmed",
      "description": "在现有用户列表中增加所属组织筛选和所属组织列。",
      "baseline": {
        "path": "02-user-management/user-list.html"
      },
      "changes": {
        "add": ["所属组织筛选", "所属组织列"],
        "modify": [],
        "delete": []
      },
      "preserve": [
        "顶部导航、侧栏和标签栏",
        "原有筛选项顺序和按钮",
        "原有表格字段、操作列、分页与密度",
        "现有交互和响应式行为"
      ],
      "allowedFiles": [
        "$page",
        "assets/prototype.css"
      ]
    }
  ]
}
```

规则：

- `baseline.path` 必须是项目内现有 HTML/JSX/Vue 页面或组件。
- `changes` 至少有一项，`preserve` 不得为空。
- `allowedFiles` 使用相对功能目录路径；`$page` 表示当前目标页面/组件。
- 脚本会复制基线文件和同功能局部资产、记录原始与准备态 hash，并生成 `incremental-contract.json`。
- 后续若修改了白名单之外的复制文件，发布检查失败。
- 基线源文件在准备后发生变化，发布检查失败，需要重新建立基线。

## 根据现有产品还原

当只有产品截图、URL、录屏或源码证据，而项目中没有已审核本地页面时，使用 reconstruction，不要伪造 incremental 基线。

先登记 evidence source：

```bash
node scripts/manage-evidence-sources.cjs add \
  --id EV-user-list --kind product-url --source https://product.example/users \
  --browser chromium \
  --viewport desktop,evidence/source-desktop.png,1440,900 \
  --viewport mobile,evidence/source-mobile.png,390,844
```

Manifest：

```json
{
  "mode": "reconstruction",
  "featureSlug": "04-user-list-reconstruction",
  "featureName": "用户列表还原",
  "pages": [{
    "title": "用户列表",
    "path": "user-list",
    "pageKey": "user-list-reconstruction",
    "requirementStatus": "confirmed",
    "description": "根据现有产品页面还原用户列表。",
    "evidenceRefs": ["EV-user-list"],
    "designDomains": ["tokens", "shell", "components", "patterns"],
    "sharedRefs": ["patterns.filter-panel", "components.data-table"]
  }]
}
```

生成结果包含 `reconstruction-contract.json`，页面初始为 `reconstruction-scaffold`。还原完成后改为 `reconstruction-authored`，再提供 reference/current 双端截图和 comparison report。

## 动态视口 evidence

截图应由真实浏览器按所选 layout profile 的 `viewports` 生成。不得自动补充桌面端或移动端；每个 `claim: fidelity` 视口都必须有对应产品证据。

增量模式至少保存：

```text
fidelity-evidence/
├── baseline-desktop.png
├── current-desktop.png
├── baseline-mobile.png
├── current-mobile.png
├── change-masks.json
└── visual-diff.json
```

Mask 文件区分本次允许变化和不稳定证据：

```json
{
  "changeMasks": {
    "desktop": [{"label": "组织筛选和所属组织列", "x": 280, "y": 120, "width": 420, "height": 620}],
    "mobile": [{"label": "组织筛选和所属组织列", "x": 0, "y": 100, "width": 120, "height": 650}]
  },
  "unstableMasks": {
    "desktop": [{"label": "当前时间", "x": 1260, "y": 20, "width": 120, "height": 32}],
    "mobile": []
  }
}
```

运行无第三方依赖的像素对比器：

```bash
python3 scripts/compare-prototype-screenshots.py \
  --viewport desktop,fidelity-evidence/baseline-desktop.png,fidelity-evidence/current-desktop.png \
  --viewport mobile,fidelity-evidence/baseline-mobile.png,fidelity-evidence/current-mobile.png \
  --masks fidelity-evidence/change-masks.json \
  --output fidelity-evidence/visual-diff.json
```

增量模式默认允许 0.1% 差异、单通道 8 级抖动和最多 35% mask。重建模式使用 `--mode reconstruction`，默认允许 2% 差异、单通道 16 级抖动，只接受 `unstableMasks`，默认最多 10%。超限必须提供 `--allow-large-mask-reason`。审核脚本记录真实指标和 hash，发布时重新验证。

## Design gap

发现现有页面、shared 或 DESIGN 无法解释的产品差异时：

```bash
node scripts/manage-design-gaps.cjs observe --id DG-001 --observed "筛选区支持折叠" --evidence EV-user-list --pages user-list
node scripts/manage-design-gaps.cjs classify --id DG-001 --classification shared-gap --proposal "增加 collapsible-filter-panel"
node scripts/manage-design-gaps.cjs confirm --id DG-001
```

实施 shared 变更后使用 `apply --files ... --registry-refs patterns.collapsible-filter-panel`，浏览器验证后使用 `verify --evidence ...`。详细状态机见 skill 的 `references/design-evolution.md`。

## DESIGN 回读条件

以下情况读取完整 DESIGN：

- 初始化或 DESIGN hash 变化；
- 修改 tokens、shared、产品壳层或模板；
- 新增 registry 中不存在的稳定组件/模式；
- 现有产品证据与 guardrails 冲突；
- 页面细节无法由现有页面、registry 和 shared 解释。

其他日常页面工作优先读取精简 context-index、guardrails、相关 registry 条目和目标页面。
