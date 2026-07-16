# Layout Integration Rules

## Contents

- 1. 先识别宿主展示模式
- 2. 安全挂载规则
- 3. 专门针对 Axure 类页面的判断提示
- 4. 专门针对 React / Vue 应用壳的判断提示
- 5. 失败兜底
- 6. 反例

这个文件用于解决一个高风险问题：

- 需求说明区虽然“追加到了页面里”，但因为宿主页面本身不在正常文档流中，最终还是压在原型内容上面

先判断展示模式，再决定说明区如何挂载。

## 1. 先识别宿主展示模式

至少先判断属于哪一类：

### 1.1 普通文档流页面

常见特征：

- 页面主体由 `section`、`main`、`article`、`card` 等正常流容器组成
- 主内容向下追加时，页面高度会自然增长
- 没有整页级 `overflow:hidden` 裁切

默认策略：

- 直接把说明区追加在主内容末尾的独立 sibling
- 保留 32px 以上的上下留白和显式分隔带

### 1.2 固定视口应用壳

常见特征：

- 根节点或布局节点含有 `h-screen`、`min-h-0`、`overflow-hidden`、`flex-1 overflow-y-auto`
- 页面内容被放进固定高度壳层，真正滚动发生在内部容器
- 常见于 React / Vue 后台管理台

默认策略：

- 不要把说明区直接追加到被裁切的滚动面板里
- 先找清楚哪一层是真正的滚动宿主，不要把“能滚动的容器”和“适合挂说明的容器”混为一谈
- 如果页面本身不是固定高度画布，而是普通主内容块，可建立外层纵向壳层，让“原页面”和“说明区”成为上下两个 sibling
- 如果页面自身已经是 `flex-1 overflow-y-auto`、多列内部滚动、固定面板 + 独立滚动区结构，默认不要继续做“上下堆叠”
- 对这类工作台页，优先使用“页面视图 / 需求说明视图”二选一切换，让原页面与说明文档在同一容器中独占显示
- 只有当你能证明页面内容本身参与外层正常文档流、且不会形成双滚动上下文时，才允许把说明区放到原页面后面

可参考的安全结构：

```html
<div class="proto-page-shell">
  <div class="proto-page-stage">
    <!-- 现有页面根节点 -->
  </div>
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
    <!-- 需求说明 -->
  </section>
  <!-- PROTO_SPEC:END page=AskData id=ask-data-spec batch=2026-04-21-run-01 visible=true source=prototype-spec-annotator -->
</div>
```

关键约束：

- `proto-page-shell` 负责纵向布局和整体滚动
- `proto-page-stage` 只包原页面，不把说明区塞进原页面已有 `main`、`panel`、`content` 的滚动裁切区

对于已经存在内部滚动的后台工作台，更推荐以下结构：

```html
<div class="proto-page-shell">
  <div class="proto-spec-switcher">
    <button type="button" data-view="page">产品页面</button>
    <button type="button" data-view="spec">需求说明</button>
  </div>

  <div class="proto-page-view" hidden>
    <!-- 原页面根节点 -->
  </div>

  <section
    class="proto-spec-doc"
    data-role="page-spec"
    data-spec-origin="prototype-spec-annotator"
    data-spec-page="AskData"
    data-spec-id="ask-data-spec"
    data-spec-batch="2026-04-21-run-01"
    data-spec-visible="true"
    hidden
  >
    <!-- 需求说明 -->
  </section>
</div>
```

这个模式的关键目标不是“把说明塞到页面后面”，而是“确保用户任一时刻只看到产品页或说明页其中之一”，从根上避免同屏遮挡。

### 1.3 绝对定位画布

常见特征：

- 存在 `#base`
- 批量 `position:absolute`
- 页面由像素级坐标摆放元素
- 常见于 Axure、低代码工具、静态原型导出

高风险信号：

- `body` 固定宽度且带 `left:-20px` 之类位移
- `#base { position:absolute; }`
- 页面背景块、卡片块、表格块都写死宽高
- 页面高度来自“最底部绝对定位元素”，而不是文档流自然撑开

默认策略：

- 不要把说明区节点直接加进 `#base`
- 不要在没有边界计算的前提下，沿用同一套绝对定位坐标，把说明区做成新的 `u12345`
- 不要仅凭“右边看起来有空白”就把说明区硬塞进画布空白区

优先采用两种安全方式之一：

#### 方式 A：建立正常流画布宿主

- 新建一个正常流 wrapper 承载原型画布
- wrapper 负责提供明确宽度和最小高度
- 让绝对定位画布继续在 wrapper 内定位
- 把说明区追加在 wrapper 后面

适用场景：

- 可以安全调整 `#base` 的外层结构
- 原型页面只有单页导出结构，没有复杂全局脚本依赖 body 级坐标

#### 方式 B：先补画布占位，再追加说明区

- 保留原始绝对定位画布不动
- 根据背景主容器或最底部元素计算原型画布的实际底部
- 在说明区前插入正常流占位容器，保证说明区从画布下方开始

适用场景：

- 直接重包 `#base` 风险较高
- 页面脚本强依赖现有 DOM 结构

#### 方式 C：建立专用安全说明带

这个方式适用于 Axure 一类“整页就是绝对定位画布”的页面，也是很多可评审原型的常见做法。

核心原则：

- 先计算现有原型已占用的边界，再把说明区放到边界之外
- 说明区可以处于独立坐标带中，但不能压在现有原型元素上
- 页面总宽高要同步扩容，确保说明区和原型都完整可见

落位顺序：

1. 先计算原型主画布的 `maxRight`、`maxBottom`
2. 如果右侧空间足够，优先放“右侧安全列”
3. 右侧不够，再放“下方安全带”
4. 放置后同步补足 `body` 或外层宿主的宽高

可参考伪代码：

```html
<div id="base">...</div>
<!-- PROTO_SPEC:BEGIN page=Workbench id=workbench-spec batch=2026-04-21-run-01 visible=true source=prototype-spec-annotator -->
<section
  id="proto-spec-root"
  class="proto-spec-doc proto-spec-axure"
  data-role="page-spec"
  data-spec-origin="prototype-spec-annotator"
  data-spec-page="Workbench"
  data-spec-id="workbench-spec"
  data-spec-batch="2026-04-21-run-01"
  data-spec-visible="true"
></section>
<!-- PROTO_SPEC:END page=Workbench id=workbench-spec batch=2026-04-21-run-01 visible=true source=prototype-spec-annotator -->
<script>
  const base = document.getElementById('base');
  const spec = document.getElementById('proto-spec-root');
  const children = [...base.children];
  const maxRight = children.reduce((m, el) => Math.max(m, el.offsetLeft + el.offsetWidth), 0);
  const maxBottom = children.reduce((m, el) => Math.max(m, el.offsetTop + el.offsetHeight), 0);
  const specWidth = 520;
  const gap = 56;
  const pageWidth = Math.max(document.body.offsetWidth, maxRight);
  const useRightRail = maxRight + gap + specWidth <= pageWidth;

  spec.style.position = 'absolute';
  spec.style.left = useRightRail ? `${maxRight + gap}px` : '40px';
  spec.style.top = useRightRail ? '40px' : `${maxBottom + gap}px`;
  document.body.style.height = 'auto';
  document.body.style.minHeight = `${maxBottom + spec.offsetHeight + 96}px`;
  document.body.style.minWidth = `${Math.max(pageWidth, maxRight + gap + specWidth + 40)}px`;
</script>
```

适用场景：

- 不方便重包 `#base`
- 但又能稳定读取页面现有占用边界
- 需要保持 Axure 原始脚本结构不变

无论选 A、B 还是 C，都必须满足：

- 方式 A / B 下，说明区是正常流块级容器
- 方式 C 下，说明区位于独立安全说明带中，而不是原型主画布占用区内
- 如果使用专用安全说明带，说明区必须完全位于原型占用边界之外
- 说明区不依赖更高 z-index 把自己“显示出来”

### 1.4 iframe / canvas / svg 嵌入页

常见特征：

- 原型主界面处在 `iframe`、`canvas`、`svg`、截图预览容器或图形画布内
- 外层常带工具栏、缩放控件、属性栏或操作提示

默认策略：

- 说明区必须挂在这些承载面的外层
- 不要试图把说明区直接写进 iframe 内层，除非你明确在改 iframe 源文件
- 不要在 canvas、svg 或截图容器之上再叠一个说明浮层

### 1.5 强覆盖层页面

常见特征：

- 页面本身含固定底栏、吸底按钮、固定页脚、抽屉、弹窗、蒙层
- 页面上方存在 `fixed inset-0` 或底部固定操作条

默认策略：

- 说明区仍然放在主页面内容之后
- 与固定底栏之间留出额外间距
- 不要把说明区写进弹窗 DOM、抽屉 DOM、蒙层 DOM
- 如果当前页面本身是“弹窗页 / 抽屉页 / 全屏侧滑层页”，也要让说明区出现在该承载面的文档层之后，而不是浮在蒙层内

## 2. 安全挂载规则

无论是什么展示模式，都要满足：

- 默认情况下，说明区必须在正常文档流中
- 说明区和原型主界面是上下关系，不是覆盖关系
- 说明区本身禁止使用 `position:fixed`
- 只有在“绝对定位画布 + 专用安全说明带”模式下，才允许说明区使用绝对定位；且必须先证明它完全处于原型占用边界之外
- 禁止用负 margin、translate、z-index 抬升来“假装”它在页面下方
- 优先在目标页面内增加局部 wrapper，不要随意改共享布局文件，除非用户明确允许跨页联动
- 新生成的说明区默认要带 `data-spec-page`、`data-spec-id`、`data-spec-batch`、`data-spec-visible` 和 `PROTO_SPEC` 注释标记

## 3. 专门针对 Axure 类页面的判断提示

如果页面同时出现以下多项，默认按“绝对定位画布”处理：

- HTML 引入 `resources/scripts/axure/*`
- 存在 `data/document.js`
- 页面主体根节点是 `#base`
- 页面 CSS 中充满 `#u1234` 这类选择器
- 背景块、卡片块、文本块大面积 `position:absolute`

这类页面最容易出现“需求说明遮挡原型内容”的问题，因为：

- `#base` 自身不参与正常文档流
- body 的可见高度未必等于画布真实底部
- 新增 sibling 如果没有占位，也会从页面顶部附近开始排
- 右侧和下方即使视觉上有空白，也不代表这些区域天然安全；必须先算边界再放置

## 4. 专门针对 React / Vue 应用壳的判断提示

如果页面出现以下多项，默认按“固定视口应用壳”处理：

- 根容器或布局组件使用 `h-screen`
- 局部使用 `overflow-hidden`
- 真实滚动发生在某个 `overflow-y-auto` 的内部容器
- 左右分栏、抽屉、属性面板依赖 flex 高度填满

这类页面最容易出现的问题不是“绝对定位遮挡”，而是：

- 说明区被塞进了一个被裁切的容器底部
- 说明区虽然存在，但滚不到、看不全，或与页面局部滚动混在一起

默认解决方式：

- 在页面外层再包一层纵向容器
- 原页面作为第一段
- 说明区作为第二段
- 外层负责整体滚动
- 不要把说明区继续塞回原页面已有 `main`、`panel`、`content` 的裁切容器里

## 5. 失败兜底

如果出现以下任一情况，默认不要强行直接改原文件：

- 无法稳定判断页面底部在哪里
- 页面高度依赖复杂脚本运行后计算
- DOM 改造后可能破坏原型交互
- 说明区只能通过 fixed overlay 才能“塞进去”
- Axure 页面无法稳定判断 `maxRight`、`maxBottom`

这时优先输出：

- 可插入的说明区片段
- 建议插入位置
- 所需 wrapper / spacer 结构说明

## 6. 反例

以下做法都应视为不合格：

- 在没有边界计算的前提下，把说明区写成和原型元素一样的绝对定位文本块
- 把说明区直接追加进 `#base`
- 把说明区塞到现有业务卡片、表单区、结果区、标签页内部
- 把说明区塞进弹窗蒙层或抽屉面板
- 把说明区加到 `overflow:hidden` 容器底部却不处理外层滚动
- 通过 `z-index`、负 margin、translate 让说明区“覆盖在页面下半部分”
