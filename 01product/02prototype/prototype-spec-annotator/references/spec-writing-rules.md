# Spec Writing Rules

## Contents

- Writing Style
- Mandatory Coverage
- 15-Dimension Evidence Scan
- Shape-Specific Coverage
- Presentation Boundary Rule
- Reversible Marker Contract
- Visibility Contract
- Secondary Surface Promotion Rule
- Secondary Surface Inventory
- Traceability Rule
- Preferred Verbs
- Anti-Patterns
- Source Protection

## Writing Style

- 标题统一用 `【模块】规则说明`、`【模块】交互规则说明`、`【模块】显示规则说明`
- 正文统一使用编号短句
- 每条规则尽量只表达一个判断或一个动作
- 文字要能直接支撑产品、设计、研发讨论

## Mandatory Coverage

每条规则优先写清：

- 触发动作
- 默认值
- 选项来源
- 校验规则
- 成功反馈
- 失败反馈
- 边界情况

如果页面中存在这些元素，还要额外补：

- 弹窗或抽屉：显示隐藏规则
- 表格或结果列表：排序、时间格式、空状态
- 状态标签：生成来源、流转条件
- 上传控件：文件类型、数量、大小、失败提示
- 风险操作：二次确认

## 15-Dimension Evidence Scan

Before finalizing a spec, scan the page with `15-dimension-scan.md`.

- Keep the normal module-based Markdown spec structure.
- Include a dimension only when it is visible, directly inferable, or supplied by the user.
- Use the scan to catch missing rules for global components, security/anti-spam, permissions, notifications, audit logs, third-party boundaries, and project metadata.
- Do not invent backend storage, permission matrices, notification templates, audit fields, or integration details from UI alone.
- If the user asks for gaps, add a compact `待补充维度` section instead of filling unknowns as facts.

## Shape-Specific Coverage

如果页面形态明确，还要补对应规则：

- 移动端：返回路径、底部固定操作、全屏弹层、弱网与空状态
- 大屏：刷新周期、时间范围、图表联动、告警或离线状态
- AIGC：输入限制、生成态、取消或重试、引用来源、结果后续操作
- 二级承载面：打开关闭、关闭后返回位置、遮罩和二次确认

## Presentation Boundary Rule

说明区的内容写法和说明区的呈现方式要同时成立：

- 需求说明区属于文档层，不属于页面真实功能层
- 默认把说明区放在原型主内容之后的独立容器中，不要塞进现有业务 card、form section、tab panel 或结果区内部
- 说明区必须参与正常文档流，不能作为 absolute / fixed 覆盖层压在原型内容上
- 如果页面属于绝对定位画布、固定视口壳层或被 `overflow:hidden` 裁切的结构，先调整宿主挂载方式，再输出说明区
- 至少提供一层显性隔断，例如留白、分隔标题、背景带、边框或提示语
- 说明区样式优先使用中性、文档化视觉，不要复用页面主按钮、状态标签、业务卡片或可交互控件样式
- 说明区 CSS 应使用独立命名空间，例如 `proto-spec-*`，避免和原页面选择器混用
- 如果输出的是 HTML 片段，也要一起输出 wrapper 和最小必要样式，保证插入后仍能一眼区分

## Reversible Marker Contract

凡是把说明区直接写回原文件，都要保证后续可精确删除。

默认要求：

- 说明区前后添加 `PROTO_SPEC:BEGIN` / `PROTO_SPEC:END` 标记
- 说明区根节点带 `data-spec-origin="prototype-spec-annotator"`
- 说明区根节点带 `data-spec-page="<PageId>"`
- 说明区根节点带唯一 `data-spec-id="<UniqueSpecId>"`
- 同一轮批量生成的说明区根节点带 `data-spec-batch="<BatchId>"`
- 说明区根节点带 `data-spec-visible="true"`，便于后续隐藏或重新显示
- 根节点继续保留 `data-role="page-spec"` 或等价说明锚点

默认命名约定：

- 如果用户没有指定 `spec-id`，默认使用 `{pageId}-spec`
- 如果用户没有指定 `batch-id`，默认使用 `spec-batch-YYYYMMDD-HHMMSS`
- 同一轮批量生成的所有说明区共享同一个 `batch-id`

推荐写法：

```html
<!-- PROTO_SPEC:BEGIN page=AppManagement id=app-management-spec batch=2026-04-21-run-01 visible=true source=prototype-spec-annotator -->
<section
  class="proto-spec-doc"
  data-role="page-spec"
  data-spec-origin="prototype-spec-annotator"
  data-spec-page="AppManagement"
  data-spec-id="app-management-spec"
  data-spec-batch="2026-04-21-run-01"
  data-spec-visible="true"
>
  ...
</section>
<!-- PROTO_SPEC:END page=AppManagement id=app-management-spec batch=2026-04-21-run-01 visible=true source=prototype-spec-annotator -->
```

如果是 JSX / TSX：

```tsx
{/* PROTO_SPEC:BEGIN page=AskData id=ask-data-spec batch=2026-04-21-run-01 visible=true source=prototype-spec-annotator */}
<section
  className="proto-spec-doc"
  data-role="page-spec"
  data-spec-origin="prototype-spec-annotator"
  data-spec-page="AskData"
  data-spec-id="ask-data-spec"
  data-spec-batch="2026-04-21-run-01"
  data-spec-visible="true"
>
  ...
</section>
{/* PROTO_SPEC:END page=AskData id=ask-data-spec batch=2026-04-21-run-01 visible=true source=prototype-spec-annotator */}
```

如果项目已经采用 `withPageSpec("PageKey", Component)` / `PageSpecDoc`：

- 优先复用该模式，不强行换成另一套插入方式
- `PageKey` 要稳定，便于后续按页面清空
- 如果能修改 `PageSpecDoc` 根节点，补上 `data-spec-origin` 和 `data-spec-page`
- 如果希望支持“按单页显隐”，优先把显隐控制做进 `PageSpecDoc` 组件本身，而不是只依赖外部删除脚本

## Visibility Contract

如果用户希望“暂时隐藏需求说明，而不是删除”，默认提供显隐能力。

推荐约束：

- 根节点使用 `data-spec-visible="true|false"`
- 隐藏时补 `hidden` 属性
- 需要运行时显隐时，在说明区分隔头部增加一个“显示需求说明 / 收起需求说明”的切换按钮
- 运行时折叠只影响说明区，不影响原型主内容

React / Vue 组件化模式推荐：

```tsx
const [specVisible, setSpecVisible] = useState(true);

<section
  className="proto-spec-doc"
  data-role="page-spec"
  data-spec-page="AskData"
  data-spec-id="ask-data-spec"
  data-spec-visible={specVisible ? "true" : "false"}
>
  <button type="button" onClick={() => setSpecVisible((v) => !v)}>
    {specVisible ? "收起需求说明" : "显示需求说明"}
  </button>
  {specVisible && <div className="proto-spec-panel">...</div>}
</section>
```

## Secondary Surface Promotion Rule

如果抽屉、弹窗、全屏侧滑层或底部弹层满足以下任一条件，应升格为单独说明段落：

- 包含独立列表、表格或结果区
- 包含独立表单、筛选或分页
- 有空状态、失败态或禁用态
- 有返回上一步、切换步骤或继续进入下一层流程
- 承载的是一个完整子任务，而不是一次轻量确认

升格后要求：

- 使用真实名称命名段落标题
- 写清显示隐藏、数据来源、关键操作、异常路径和返回路径
- 不要只在主页面的 `【功能操作】` 中用一两句带过

## Secondary Surface Inventory

开始写说明前，应先列出页面中的全部二级承载面，例如：

- 新建抽屉
- 编辑弹窗
- 授权抽屉
- 添加数据二级抽屉

然后逐个判断：

- 是否只承载轻量确认或只读信息
- 是否已经形成独立子任务

凡是符合升格条件的承载面，都必须单独出说明；不能因为已经写了一个复杂抽屉，就遗漏同页里的其他复杂抽屉。

## Traceability Rule

说明必须从页面真实元素反推：

- 页面上出现的关键模块，应在说明区里找到对应规则
- 说明里提到的字段、按钮、状态、分栏、弹层，页面中必须能找到对应元素
- 若某项业务规则页面中不可见且用户也未补充，不要强行写死

## Preferred Verbs

优先使用明确动作词：

- 点击
- 打开
- 关闭
- 弹出
- 展示
- 隐藏
- 默认
- 校验
- 提示
- 提交
- 刷新
- 跳转

## Anti-Patterns

避免以下写法：

- 提升效率
- 优化体验
- 支持灵活配置
- 用户可按需处理
- 具体规则可自行定义
- 暂不考虑异常情况

这类句子没有页面约束力，不能作为说明区正文。

## Source Protection

必须遵守：

- 不引用任何隐藏来源项目名称
- 不引用隐藏来源页面名称
- 不引用来源文件路径
- 不复制来源页面原文

允许做的事：

- 复用结构组织方法
- 复用页面类型划分
- 复用写作格式
- 复用“页面即文档”的交付策略
