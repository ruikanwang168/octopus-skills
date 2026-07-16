# Presentation Boundary Rules

需求说明区是“文档层”，不是页面新增业务模块。

## Default Placement

- 默认把说明区追加在原型主内容结束后，作为独立 sibling 容器，而不是插入现有业务卡片、标签页内容、表单分组或结果区内部。
- 如果页面存在吸底操作栏、固定底栏或悬浮操作区，说明区仍应属于主滚动内容末尾，并与固定操作区保留明显间距。
- 如果用户只要可插入片段，也要输出完整 wrapper，而不是只吐几个标题和列表项。

## Document Flow Safety

- 说明区本身必须处在正常文档流中，禁止用 `position:absolute`、`position:fixed` 或负位移把它压在原型画布上。
- 如果页面宿主存在 `#base`、大量绝对定位、`h-screen`、`overflow-hidden` 等高风险结构，先按 `layout-integration-rules.md` 选择安全挂载方式，再输出说明区。
- 只要原型主内容本身不参与正常文档流，就不能直接假设“追加 sibling”一定安全；必须先解决宿主高度、滚动或画布占位问题。
- 对 `h-screen` / `overflow-hidden` / 多列独立滚动的后台工作台，默认使用“页面视图 / 需求说明视图”切换，不让产品页与说明区同屏堆叠。
- 只有在 Axure / 绝对定位画布的“专用安全说明带”模式下，才允许说明区使用绝对定位；且必须先证明它完全位于原型占用边界之外。
- iframe、canvas、svg 画布类页面，说明区只能挂在承载面的外层，不能覆盖在承载层之上。

## Boundary Signals

至少提供一层肉眼可见的隔断，让阅读者一眼看出“这里开始是需求说明，不是原型界面”：

- 32px 以上的上下留白
- 独立分隔标题，例如 `需求说明`、`页面规则说明`
- 独立背景带、描边、阴影或纸面色块
- 一句提示语，例如“以下内容为页面需求说明，不属于原型操作界面”

不要只把说明区当成页面里的又一个普通业务 section。

## Visual Style

- 优先使用中性、文档化视觉，例如灰白、蓝灰、纸面色，而不是继续沿用页面业务主色。
- 不要复用原页面的主按钮、状态 badge、业务卡片、表单控件样式，让说明区看起来像还能继续操作。
- 说明区标题层级、段落密度和表格样式应服务于阅读，不应模拟真实业务控件。

## CSS Isolation

- 为说明区使用独立命名空间，例如 `proto-spec-*`、`page-spec-*`。
- 避免直接复用页面已有选择器名，例如 `card`、`panel`、`section-card`、`status-badge`、`btn-primary`。
- 如果页面已有复杂全局样式，优先在说明区 wrapper 下写限定选择器，降低样式串扰。

## Recommended Skeleton

可优先采用以下结构：

```html
<!-- PROTO_SPEC:BEGIN page=AskData id=ask-data-spec batch=2026-04-21-run-01 visible=true source=prototype-spec-annotator -->
<section
  class="proto-spec-doc"
  data-role="page-spec"
  data-spec-origin="prototype-spec-annotator"
  data-spec-page="AskData"
  data-spec-id="ask-data-spec"
  data-spec-batch="2026-04-21-run-01"
  data-spec-visible="true"
>
  <div class="proto-spec-divider">
    <span class="proto-spec-eyebrow">需求说明</span>
    <button type="button" class="proto-spec-toggle">收起需求说明</button>
    <h2>页面规则说明</h2>
    <p>以下内容为页面需求说明，不属于原型操作界面。</p>
  </div>

  <div class="proto-spec-panel">
    <!-- 各模块规则说明 -->
  </div>
</section>
<!-- PROTO_SPEC:END page=AskData id=ask-data-spec batch=2026-04-21-run-01 visible=true source=prototype-spec-annotator -->
```

其中：

- `proto-spec-doc` 负责与原型主内容拉开距离
- `proto-spec-divider` 负责建立“原型结束，文档开始”的视觉信号
- `proto-spec-panel` 负责承载章节正文
- `proto-spec-toggle` 负责在用户要求时提供运行时显隐入口

## Marker Discipline

新生成的说明区默认遵守：

- `data-spec-page` 标识页面
- `data-spec-id` 标识单个说明实例
- `data-spec-batch` 标识一轮批量生成
- `data-spec-visible` 标识默认显示状态
- `PROTO_SPEC:BEGIN / END` 注释与根节点属性保持一致

## Anti-Patterns

避免以下做法：

- 把说明区直接做成与原型正文完全同款的业务卡片
- 把说明区塞进“基本信息”“结果区”“详情卡片”等现有业务 section 里
- 复用页面的主按钮、状态标签、表单输入框样式来排版说明文案
- 让说明区看起来像页面还在继续编辑或继续操作
- 把说明区做成 `fixed` 底部栏、右侧浮层、抽屉或蒙版，直接覆盖原型主界面
- 把说明区塞进会裁切内容的 `overflow:hidden` 容器，导致说明或原型互相遮挡
- 对已经存在内部滚动的工作台页，仍继续采用“页面在上、说明在下”的堆叠模式，制造双滚动上下文和视觉重叠
