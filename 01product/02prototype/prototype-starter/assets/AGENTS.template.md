# {{PRODUCT_NAME}}原型项目规则

目标是还原已确认的产品事实，不是生成通用后台。任何业务文案、数据、视觉值和布局规则都必须来自 DESIGN、产品证据或用户确认。

## 开始工作

先读 `design-system/context-index.json` 和 `design-system/authoring-context.json`。布局契约 v2 项目只加载当前页面 `layoutProfile` 指向的 `design-system/contexts/layout/<profile>.json`：

- `design-system`：首次 shared 建设、DESIGN 变化或稳定模式调整。
- `new-feature`：复用现有壳层和模式的新页面。
- `reconstruction`：有截图、URL 或源码证据，但没有本地已审核基线。
- `incremental`：已有页面上的升级、优化或字段调整。
- `verification`：检查和发布。

`design-contract.json` 与 `check-rules.json` 只供脚本读取。只有首次 shared authoring、确认的设计缺口或精简上下文冲突时才回读完整 DESIGN；不要同时加载完整 DESIGN、contract、guardrails、registry 和所有 shared/template。

## 事实与证据门禁

- DESIGN 不充分时停止，向用户确认，更新原始 DESIGN 和 `evidence.decisions` 后重新预检。
- 不得添加未声明的导航、页面、字段、按钮、人员、日期或示例数据。
- `existing-product`/`reconstruction` 必须覆盖所选 profile 中所有 `claim: fidelity` 的视口；不得额外要求未声明的桌面端或移动端。
- 证据优先级：生产源码/设计变量 > 现有产品页面 > 截图或录屏 > 已审核原型 > DESIGN > 本次需求。

## 设计系统与布局

只 author `representative: true` 的模板。每个代表页面只能有一个产品根节点；顶栏、侧栏、工作页签、底部导航、页脚等区域是否存在完全由布局 profile 决定。所有视口均为 `absent` 的区域不得进入产品 DOM。开发入口和审计控件必须位于产品根节点外。

```bash
node scripts/prepare-layout-audit.cjs
python3 -m http.server 8000
```

在 `design-system/layout-audit.html` 运行 manifest 声明的全部视口和断点边界检查，把报告保存为 `design-system/layout-report.json`，并按 manifest 的精确尺寸截取原始代表页面。随后执行：

```bash
node scripts/finalize-design-system.cjs --manifest design-system/preview-manifest.json
```

页面、shared、布局模型、契约、报告或截图改变后，旧 evidence 自动失效。证据工具优先使用可重复的 `--viewport`；旧版 `--desktop/--mobile` 仅作兼容输入。

## 功能变更

- 信息不完整的页面保持 placeholder；不得用 scaffold 冒充完成页面。
- incremental 必须提供 `baseline.path`、`changes`、`preserve` 和 `allowedFiles`，从基线复制并验证允许区域外没有变化。
- reconstruction 先登记 evidence，manifest 使用 `evidenceRefs`，完成后提供 reference/current 双端截图和 comparison report。
- shared 模式须有两个功能复用证据或 DESIGN 明确定义；使用 design gap 流程记录冲突，不凭单次截图改写 DESIGN。

详细 manifest、审核和差异报告格式见 `docs/prototype-workflows.md`。

## 发布

```bash
node scripts/check-prototype-compliance.cjs --release
```

发布检查会拒绝 placeholder/scaffold、过期 hash、缺失布局证据、伪截图、增量白名单外改动和未解决的确认缺口。

{{FRAMEWORK_RULES}}

当前代表页面：

{{PAGE_TEMPLATE_LIST}}

当前自检项：

{{SELF_CHECK_LIST}}
