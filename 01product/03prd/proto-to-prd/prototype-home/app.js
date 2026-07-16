const phases = [
  { id: "discovery", name: "01 需求与洞察", top: 20 },
  { id: "definition", name: "02 产品定义", top: 114 },
  { id: "design", name: "03 原型与规格", top: 208 },
  { id: "engineering", name: "04 研发实现", top: 302 },
  { id: "delivery", name: "05 验收上线", top: 396 },
  { id: "growth", name: "06 宣传增长", top: 490 }
];

const nodes = [
  {
    id: "collect",
    title: "需求收集",
    phase: "discovery",
    required: true,
    x: 28,
    y: 44,
    summary: "聚合访谈、会议、售前材料和业务描述。",
    tags: ["访谈", "素材"],
    intro: "把零散业务信息收束成可继续分析的需求输入，避免一上来就写方案。",
    scenarios: ["客户访谈后需要整理需求", "售前沟通材料需要转成研发输入", "已有想法但边界仍然模糊"],
    input: {
      desc: "会议纪要、访谈记录、客户业务描述、截图或已有材料。",
      example: "examples/discovery-notes.md"
    },
    process: ["抽取业务对象、角色和关键事件", "识别用户目标、约束、疑问和待确认事项", "沉淀为结构化需求素材"],
    output: {
      desc: "业务需求素材包、待澄清问题清单、角色与场景草稿。",
      example: "examples/requirement-intake.md"
    },
    resources: [
      ["biz-brief", "skill://biz-brief"],
      ["访谈记录模板", "../assets/agent-story-template.md"]
    ]
  },
  {
    id: "brief",
    title: "业务梳理",
    phase: "discovery",
    required: true,
    x: 242,
    y: 44,
    summary: "把输入整理成可评审的业务需求文档。",
    tags: ["PRD前置", "评审"],
    intro: "将原始素材转为业务视角的需求梳理文档，先讲清业务，再进入产品设计。",
    scenarios: ["需求仍停留在口头描述", "多人对业务问题理解不一致", "需要给产品或研发做评审输入"],
    input: {
      desc: "需求收集节点输出的素材包、业务目标、当前痛点。",
      example: "examples/business-brief-input.md"
    },
    process: ["归纳业务背景与目标", "抽象用户角色、关键场景与业务规则", "输出问题、价值和范围边界"],
    output: {
      desc: "《业务需求梳理文档》与待确认事项。",
      example: "examples/business-brief.md"
    },
    resources: [
      ["biz-brief", "skill://biz-brief"],
      ["业务梳理模板", "templates/business-brief.md"]
    ]
  },
  {
    id: "research",
    title: "开源/竞品调研",
    phase: "discovery",
    required: false,
    x: 456,
    y: 44,
    summary: "检索可参考方案，判断自研、复用或定制路线。",
    tags: ["调研", "可选"],
    intro: "在需求进入产品定义前，先看可复用的开源项目、竞品能力和行业实现方式。",
    scenarios: ["想找开源系统作为内部参考", "需要评估是否已有成熟方案", "需要为方案设计提供证据"],
    input: {
      desc: "关键词、目标业务领域、技术偏好、必须具备的功能。",
      example: "examples/oss-research-input.md"
    },
    process: ["检索 GitHub/Gitee 候选项目", "比较功能、活跃度、技术栈与适配风险", "给出优先推荐和使用边界"],
    output: {
      desc: "开源/竞品调研文档、候选清单、优先推荐方案。",
      example: "examples/oss-research-report.md"
    },
    resources: [
      ["oss-research", "skill://oss-research"],
      ["调研对比模板", "templates/research-comparison.md"]
    ]
  },
  {
    id: "prd",
    title: "PRD生成",
    phase: "definition",
    required: true,
    x: 242,
    y: 138,
    summary: "生成产品说明、用户故事与AI开发说明。",
    tags: ["PRD", "AI说明"],
    intro: "把业务梳理结果转成产品可评审、研发可执行的需求文档。",
    scenarios: ["需要从模糊需求生成PRD", "需要给AI开发工具明确实现范围", "旧需求需要重写成更可执行的版本"],
    input: {
      desc: "业务需求梳理文档、关键页面或功能清单、业务规则。",
      example: "../references/ai-product-prd-template.md"
    },
    process: ["识别需求模式与增量范围", "生成PRD草案、流程和验收口径", "同步生成AI开发说明书"],
    output: {
      desc: "PRD草案、痛点与方案分析、AI开发说明书。",
      example: "../references/traditional-prd-template.md"
    },
    resources: [
      ["xuqiu-analyzer", "skill://xuqiu-analyzer"],
      ["product-spec-generator", "skill://product-spec-generator"],
      ["PRD检查清单", "../assets/prd-validation-checklist.md"]
    ]
  },
  {
    id: "story",
    title: "研发需求清单",
    phase: "definition",
    required: true,
    x: 456,
    y: 138,
    summary: "拆成用户故事、功能需求和研发任务。",
    tags: ["拆解", "验收"],
    intro: "将PRD进一步拆解为研发可排期、可验收、可追踪的需求清单。",
    scenarios: ["需要进入排期或任务拆分", "需要明确字段、交互和业务规则", "需要把用户故事和研发需求分开表达"],
    input: {
      desc: "PRD草案、页面或能力范围、目标验收结果。",
      example: "examples/prd-to-dev-list.md"
    },
    process: ["抽象业务价值为用户故事", "拆解功能需求和研发处理规则", "补齐字段、状态、数据落点与验收结果"],
    output: {
      desc: "产品研发需求清单、用户故事、研发需求条目。",
      example: "examples/dev-requirements.md"
    },
    resources: [
      ["requirements-spec-generator", "skill://requirements-spec-generator"],
      ["研发需求模板", "templates/dev-requirements.md"]
    ]
  },
  {
    id: "acceptance",
    title: "验收口径",
    phase: "definition",
    required: true,
    x: 670,
    y: 138,
    summary: "把需求转成可测试、可评审的通过标准。",
    tags: ["验收", "质量"],
    intro: "在进入原型和研发前提前定义通过标准，减少交付阶段才发现口径不一致。",
    scenarios: ["PRD需要补验收标准", "团队需要统一完成定义", "AI开发说明需要明确判断结果"],
    input: {
      desc: "PRD、功能需求清单、关键业务规则、异常场景。",
      example: "../assets/prd-validation-checklist.md"
    },
    process: ["提取核心用户路径", "拆解正常、异常、边界和权限规则", "形成可执行验收清单"],
    output: {
      desc: "功能验收标准、测试关注点、发布前检查项。",
      example: "examples/acceptance-criteria.md"
    },
    resources: [
      ["requirements-spec-generator", "skill://requirements-spec-generator"],
      ["PRD验证清单", "../assets/prd-validation-checklist.md"]
    ]
  },
  {
    id: "ideate",
    title: "视觉探索",
    phase: "design",
    required: false,
    x: 242,
    y: 232,
    summary: "生成多个首页或关键流程视觉方向。",
    tags: ["设计", "可选"],
    intro: "当产品没有明确视觉来源时，先探索几种可选方向，再进入原型或页面实现。",
    scenarios: ["新产品没有设计系统", "需要给团队选择首页方向", "需要从模糊想法变成可讨论的界面"],
    input: {
      desc: "产品目标、目标用户、视觉偏好、交互深度。",
      example: "examples/design-brief.md"
    },
    process: ["确认设计简报", "生成多套视觉方向", "收敛为选定视觉目标"],
    output: {
      desc: "视觉方向方案、关键页面 mock、可继续实现的设计目标。",
      example: "examples/visual-options.md"
    },
    resources: [
      ["product-design:ideate", "skill://product-design:ideate"],
      ["设计简报模板", "templates/design-brief.md"]
    ]
  },
  {
    id: "prototype",
    title: "原型标注",
    phase: "design",
    required: false,
    x: 456,
    y: 232,
    summary: "为页面原型补页面级说明和交互规则。",
    tags: ["页面级", "可选"],
    intro: "当已有HTML、Vue或React原型时，为页面补充可维护的Markdown需求说明资产。",
    scenarios: ["已有原型但缺少说明", "需要把页面说明展示在原型里", "需要迁移旧inline说明"],
    input: {
      desc: "现有原型项目、页面路由、页面截图或现有说明。",
      example: "examples/prototype-pages.md"
    },
    process: ["识别页面与稳定pageKey", "生成页面级说明", "维护registry与history"],
    output: {
      desc: "页面级Markdown说明、registry、可选说明展示层。",
      example: "examples/page-spec.md"
    },
    resources: [
      ["prototype-spec-annotator", "skill://prototype-spec-annotator"],
      ["页面说明模板", "templates/page-spec.md"]
    ]
  },
  {
    id: "designSystem",
    title: "设计规范",
    phase: "design",
    required: false,
    x: 670,
    y: 232,
    summary: "生成设计系统、预览页与风格差距记录。",
    tags: ["视觉", "规范"],
    intro: "在缺少稳定设计语言时，先形成可执行的设计系统包，减少研发阶段的视觉返工。",
    scenarios: ["新产品需要统一视觉语言", "已有参考但缺少设计规范", "前端需要明确组件与样式准则"],
    input: {
      desc: "产品定位、视觉参考、品牌偏好、已有页面或截图。",
      example: "examples/design-source.md"
    },
    process: ["提炼设计原则与组件基线", "生成明暗预览和示例页", "记录无法确定的设计空缺"],
    output: {
      desc: "DESIGN.md、preview.html、example.html、DESIGN_GAPS.md。",
      example: "examples/design-system-package.md"
    },
    resources: [
      ["design-generator", "skill://design-generator"],
      ["UI模式库", "../references/ui-patterns.md"]
    ]
  },
  {
    id: "tech",
    title: "技术方案",
    phase: "engineering",
    required: true,
    x: 456,
    y: 326,
    summary: "确定架构、模块边界、数据与集成方案。",
    tags: ["架构", "方案"],
    intro: "在进入编码前明确技术选型、模块边界、数据流、接口和风险。",
    scenarios: ["需求涉及多系统集成", "需要给AI编码工具明确实现路径", "需要评估风险和工期"],
    input: {
      desc: "PRD、研发需求清单、现有项目结构、约束条件。",
      example: "examples/technical-plan-input.md"
    },
    process: ["分析现有架构和边界", "设计模块、数据和API方案", "形成可执行任务计划"],
    output: {
      desc: "技术方案、实现任务拆解、风险与依赖清单。",
      example: "examples/technical-plan.md"
    },
    resources: [
      ["software-dev-agent", "skill://software-dev-agent"],
      ["技术方案模板", "templates/technical-plan.md"]
    ]
  },
  {
    id: "build",
    title: "开发执行",
    phase: "engineering",
    required: true,
    x: 670,
    y: 326,
    summary: "按说明书修改代码、补交互和状态。",
    tags: ["编码", "实现"],
    intro: "把研发需求与技术方案落到代码中，持续按项目规范验证。",
    scenarios: ["需要从需求直接实现功能", "需要在已有项目中做增量开发", "需要补齐交互、状态和数据处理"],
    input: {
      desc: "AI开发说明书、技术方案、代码仓库、测试命令。",
      example: "examples/build-task.md"
    },
    process: ["读取项目结构与规则", "小步实现功能与交互", "运行测试、修复问题并记录变更"],
    output: {
      desc: "代码变更、可运行页面、测试结果和交付说明。",
      example: "examples/build-summary.md"
    },
    resources: [
      ["software-dev-agent", "skill://software-dev-agent"],
      ["编码提示词模板", "../assets/prompt-design-template.md"]
    ]
  },
  {
    id: "review",
    title: "代码审查",
    phase: "engineering",
    required: true,
    x: 884,
    y: 326,
    summary: "检查质量、安全、回归和测试缺口。",
    tags: ["质量", "风险"],
    intro: "以代码审查视角优先发现会导致线上问题的缺陷，而不是泛泛点评。",
    scenarios: ["功能完成后需要合并前审查", "需要检查安全和性能风险", "需要补齐测试建议"],
    input: {
      desc: "代码diff、变更目标、测试结果、关键风险点。",
      example: "examples/code-review-input.md"
    },
    process: ["读取相关上下文", "按严重级别定位问题", "给出修复建议和测试缺口"],
    output: {
      desc: "审查发现、风险等级、文件行号、建议修复方案。",
      example: "examples/code-review-report.md"
    },
    resources: [
      ["code-review-agent", "skill://code-review-agent"],
      ["审查清单", "templates/code-review-checklist.md"]
    ]
  },
  {
    id: "testCases",
    title: "测试用例",
    phase: "delivery",
    required: true,
    x: 456,
    y: 420,
    summary: "把验收口径落成测试路径和边界用例。",
    tags: ["测试", "用例"],
    intro: "在正式验收前，先把功能路径、异常状态、数据边界和回归点组织成测试用例。",
    scenarios: ["验收标准较多需要系统执行", "功能有多个角色或权限", "需要给测试或AI执行工具明确步骤"],
    input: {
      desc: "验收标准、研发需求清单、可运行环境、测试数据。",
      example: "examples/test-case-input.md"
    },
    process: ["映射主流程和分支流程", "补齐异常、空状态、权限和边界值", "标注前置条件与期望结果"],
    output: {
      desc: "测试用例清单、回归范围、阻塞级别定义。",
      example: "examples/test-cases.md"
    },
    resources: [
      ["software-dev-agent", "skill://software-dev-agent"],
      ["测试用例模板", "templates/test-cases.md"]
    ]
  },
  {
    id: "qa",
    title: "测试验收",
    phase: "delivery",
    required: true,
    x: 884,
    y: 420,
    summary: "验证功能、视觉、数据和异常状态。",
    tags: ["测试", "验收"],
    intro: "把PRD验收口径转为可执行检查，覆盖功能、视觉、数据、边界和回归。",
    scenarios: ["发布前需要验收", "页面改动需要视觉检查", "流程有异常和空状态"],
    input: {
      desc: "验收标准、可运行环境、测试账号、变更范围。",
      example: "examples/qa-input.md"
    },
    process: ["映射验收点", "执行功能与视觉检查", "记录阻塞问题和修复回归"],
    output: {
      desc: "验收报告、问题清单、通过或阻塞结论。",
      example: "examples/qa-report.md"
    },
    resources: [
      ["product-design:audit", "skill://product-design:audit"],
      ["PRD验证清单", "../assets/prd-validation-checklist.md"]
    ]
  },
  {
    id: "launch",
    title: "上线交付",
    phase: "delivery",
    required: true,
    x: 670,
    y: 420,
    summary: "准备发布说明、部署检查和交付文档。",
    tags: ["发布", "交付"],
    intro: "确保功能从可用走到可交付，补齐发布、回滚、培训和交接材料。",
    scenarios: ["测试通过后准备上线", "需要交付给客户或团队使用", "需要保留发布记录"],
    input: {
      desc: "验收报告、部署目标、版本说明、交付对象。",
      example: "examples/launch-input.md"
    },
    process: ["整理上线清单", "确认部署与回滚路径", "生成交付说明和培训材料"],
    output: {
      desc: "发布说明、部署清单、交付文档、培训材料。",
      example: "examples/launch-note.md"
    },
    resources: [
      ["lark-doc", "skill://lark-doc"],
      ["交付清单模板", "templates/delivery-checklist.md"]
    ]
  },
  {
    id: "docs",
    title: "知识沉淀",
    phase: "growth",
    required: false,
    x: 456,
    y: 514,
    summary: "把交付材料沉淀为团队可复用知识资产。",
    tags: ["文档", "知识库"],
    intro: "上线之后把产品说明、操作手册、决策记录和复盘材料沉淀到知识库，服务后续迭代。",
    scenarios: ["项目交付后需要培训或交接", "团队需要复用这次研发经验", "需要形成可检索的模板和SOP"],
    input: {
      desc: "发布说明、交付文档、问题复盘、项目决策记录。",
      example: "examples/knowledge-input.md"
    },
    process: ["整理交付资产", "抽取可复用模板和SOP", "沉淀到文档或知识库空间"],
    output: {
      desc: "知识库文章、SOP、模板索引、复盘记录。",
      example: "examples/knowledge-base.md"
    },
    resources: [
      ["lark-doc", "skill://lark-doc"],
      ["lark-wiki", "skill://lark-wiki"],
      ["知识沉淀模板", "templates/knowledge-base.md"]
    ]
  },
  {
    id: "marketing",
    title: "产品宣传",
    phase: "growth",
    required: false,
    x: 670,
    y: 514,
    summary: "生成对外介绍、卖点、素材和发布话术。",
    tags: ["增长", "内容"],
    intro: "把产品能力转成面向目标用户的价值表达，用于官网、社媒、闲鱼或销售材料。",
    scenarios: ["新功能上线需要宣传", "定制服务需要卖点文案", "需要生成主图或物料提示词"],
    input: {
      desc: "产品说明、目标用户、功能截图、差异化卖点。",
      example: "examples/marketing-input.md"
    },
    process: ["提炼目标人群和痛点", "转写卖点与功能介绍", "生成素材清单和图片提示词"],
    output: {
      desc: "标题、卖点文案、适用人群、宣传素材提示词。",
      example: "examples/marketing-copy.md"
    },
    resources: [
      ["xianyu-software", "skill://xianyu-software"],
      ["宣传文案模板", "templates/marketing-copy.md"]
    ]
  },
  {
    id: "feedback",
    title: "反馈复盘",
    phase: "growth",
    required: true,
    x: 884,
    y: 514,
    summary: "收集上线反馈，回流到需求或优化节点。",
    tags: ["复盘", "回环"],
    intro: "将上线后的用户反馈、数据和运营观察沉淀为下一轮迭代输入。",
    scenarios: ["上线后出现新问题", "宣传后收集到用户反馈", "需要规划下一轮迭代"],
    input: {
      desc: "用户反馈、埋点数据、客服记录、销售反馈。",
      example: "examples/feedback-input.md"
    },
    process: ["分类反馈和影响范围", "判断是否进入修复、优化或新需求", "回流到需求梳理或研发需求"],
    output: {
      desc: "复盘报告、优化建议、下一轮需求池。",
      example: "examples/retrospective.md"
    },
    resources: [
      ["biz-brief", "skill://biz-brief"],
      ["复盘模板", "templates/retrospective.md"]
    ]
  }
];

const edges = [
  ["collect", "brief", "normal"],
  ["brief", "research", "conditional"],
  ["research", "prd", "normal"],
  ["brief", "prd", "normal"],
  ["prd", "story", "normal"],
  ["story", "acceptance", "normal"],
  ["acceptance", "ideate", "conditional"],
  ["acceptance", "prototype", "conditional"],
  ["acceptance", "tech", "normal"],
  ["ideate", "prototype", "normal"],
  ["prototype", "designSystem", "conditional"],
  ["designSystem", "tech", "normal"],
  ["tech", "build", "normal"],
  ["build", "review", "normal"],
  ["review", "testCases", "normal"],
  ["testCases", "qa", "normal"],
  ["qa", "launch", "normal"],
  ["launch", "docs", "normal"],
  ["docs", "marketing", "conditional"],
  ["launch", "marketing", "conditional"],
  ["marketing", "feedback", "normal"],
  ["feedback", "brief", "loop"],
  ["review", "build", "loop"],
  ["qa", "build", "loop"],
  ["testCases", "story", "loop"]
];

const state = {
  selectedId: null,
  activeTab: "overview",
  filter: "all",
  hideOptional: false,
  search: ""
};

const roadmap = document.querySelector("#roadmap");
const detailEmpty = document.querySelector("#detailEmpty");
const detailCard = document.querySelector("#detailCard");
const detailStage = document.querySelector("#detailStage");
const detailTitle = document.querySelector("#detailTitle");
const detailStatus = document.querySelector("#detailStatus");
const detailContent = document.querySelector("#detailContent");
const libraryGrid = document.querySelector("#libraryGrid");
const searchInput = document.querySelector("#searchInput");
const configDialog = document.querySelector("#configDialog");

function nodeById(id) {
  return nodes.find((node) => node.id === id);
}

function phaseName(id) {
  return phases.find((phase) => phase.id === id)?.name ?? id;
}

function createRoadmap() {
  const inner = document.createElement("div");
  inner.className = "roadmap-inner";

  phases.forEach((phase) => {
    const lane = document.createElement("div");
    lane.className = "phase-lane";
    lane.style.setProperty("--lane-top", `${phase.top}px`);
    lane.innerHTML = `<span class="phase-label">${phase.name}</span>`;
    inner.appendChild(lane);
  });

  edges.forEach(([from, to, type]) => {
    const source = nodeById(from);
    const target = nodeById(to);
    if (!source || !target) return;
    const line = makeLine(source, target, type);
    inner.appendChild(line);
  });

  nodes.forEach((node) => {
    const button = document.createElement("button");
    button.className = "node-card";
    button.type = "button";
    button.dataset.id = node.id;
    button.style.setProperty("--x", `${node.x}px`);
    button.style.setProperty("--y", `${node.y}px`);
    button.innerHTML = `
      <span class="node-topline">
        <span class="node-type ${node.required ? "required" : "optional"}">${node.required ? "必做" : "条件"}</span>
        <span class="node-meta"><span>${node.tags[0]}</span></span>
      </span>
      <span class="node-title">${node.title}</span>
      <span class="node-desc">${node.summary}</span>
    `;
    button.addEventListener("click", () => selectNode(node.id));
    inner.appendChild(button);
  });

  roadmap.replaceChildren(inner);
  applyFilters();
}

function makeLine(source, target, type) {
  const line = document.createElement("span");
  line.className = `flow-line ${type === "loop" ? "loop" : ""} ${type === "conditional" ? "conditional" : ""}`;

  const sourceX = source.x + 176;
  const sourceY = source.y + 43;
  const targetX = target.x;
  const targetY = target.y + 43;
  const dx = targetX - sourceX;
  const dy = targetY - sourceY;
  const length = Math.max(38, Math.hypot(dx, dy));
  const angle = Math.atan2(dy, dx) * (180 / Math.PI);

  line.style.left = `${sourceX + 8}px`;
  line.style.top = `${sourceY}px`;
  line.style.width = `${length - 16}px`;
  line.style.height = "2px";
  line.style.transform = `rotate(${angle}deg)`;
  return line;
}

function selectNode(id) {
  state.selectedId = id;
  state.activeTab = "overview";
  renderDetail();
  updateSelectedNode();
}

function updateSelectedNode() {
  document.querySelectorAll(".node-card").forEach((card) => {
    card.classList.toggle("is-selected", card.dataset.id === state.selectedId);
  });
}

function renderDetail() {
  const node = nodeById(state.selectedId);
  if (!node) {
    detailEmpty.hidden = false;
    detailCard.hidden = true;
    return;
  }

  detailEmpty.hidden = true;
  detailCard.hidden = false;
  detailStage.textContent = phaseName(node.phase);
  detailTitle.textContent = node.title;
  detailStatus.textContent = node.required ? "必做节点" : "条件节点";
  detailStatus.classList.toggle("optional", !node.required);

  document.querySelectorAll(".tab-list button").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.tab === state.activeTab);
  });

  detailContent.innerHTML = detailTemplate(node, state.activeTab);
}

function detailTemplate(node, tab) {
  const list = (items) => `<ul>${items.map((item) => `<li>${item}</li>`).join("")}</ul>`;
  if (tab === "overview") {
    return `
      <h3>介绍</h3>
      <p>${node.intro}</p>
      <h3>使用场景</h3>
      ${list(node.scenarios)}
    `;
  }
  if (tab === "input") {
    return `
      <h3>输入描述</h3>
      <p>${node.input.desc}</p>
      <div class="resource-list">
        <a href="${node.input.example}">输入示例地址 <span>${node.input.example}</span></a>
      </div>
    `;
  }
  if (tab === "process") {
    return `
      <h3>处理流程说明</h3>
      ${list(node.process)}
    `;
  }
  if (tab === "output") {
    return `
      <h3>输出描述</h3>
      <p>${node.output.desc}</p>
      <div class="resource-list">
        <a href="${node.output.example}">输出示例地址 <span>${node.output.example}</span></a>
      </div>
    `;
  }
  return `
    <h3>skills 与工具地址</h3>
    <div class="resource-list">
      ${node.resources.map(([label, href]) => `<a href="${href}">${label}<span>${href}</span></a>`).join("")}
    </div>
  `;
}

function applyFilters() {
  const query = state.search.trim().toLowerCase();
  document.querySelectorAll(".node-card").forEach((card) => {
    const node = nodeById(card.dataset.id);
    const text = [
      node.title,
      node.summary,
      node.intro,
      node.tags.join(" "),
      node.resources.map((item) => item.join(" ")).join(" ")
    ]
      .join(" ")
      .toLowerCase();

    const typeMatch =
      state.filter === "all" ||
      (state.filter === "required" && node.required) ||
      (state.filter === "optional" && !node.required);
    const optionalMatch = !state.hideOptional || node.required;
    const queryMatch = !query || text.includes(query);

    card.classList.toggle("is-hidden", !optionalMatch);
    card.classList.toggle("is-muted", optionalMatch && (!typeMatch || !queryMatch));
  });
}

function renderLibrary() {
  const picks = ["research", "prd", "ideate", "prototype", "tech", "review", "testCases", "marketing"];
  libraryGrid.innerHTML = picks
    .map((id) => {
      const node = nodeById(id);
      return `
        <article class="library-card">
          <span class="node-type ${node.required ? "required" : "optional"}">${node.required ? "必做" : "条件"}</span>
          <h3>${node.title}</h3>
          <p>${node.summary}</p>
          <a href="#" data-library-node="${node.id}">查看节点详情</a>
        </article>
      `;
    })
    .join("");

  libraryGrid.querySelectorAll("[data-library-node]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      selectNode(link.dataset.libraryNode);
      document.querySelector(".detail-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

document.querySelectorAll(".segmented button").forEach((button) => {
  button.addEventListener("click", () => {
    state.filter = button.dataset.filter;
    document.querySelectorAll(".segmented button").forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
    applyFilters();
  });
});

document.querySelectorAll(".tab-list button").forEach((button) => {
  button.addEventListener("click", () => {
    state.activeTab = button.dataset.tab;
    renderDetail();
  });
});

searchInput.addEventListener("input", (event) => {
  state.search = event.target.value;
  applyFilters();
});

document.querySelector("#toggleOptional").addEventListener("click", (event) => {
  state.hideOptional = !state.hideOptional;
  event.currentTarget.textContent = state.hideOptional ? "显示可选" : "隐藏可选";
  applyFilters();
});

document.querySelector("#resetView").addEventListener("click", () => {
  state.selectedId = null;
  state.activeTab = "overview";
  updateSelectedNode();
  renderDetail();
});

document.querySelector("#densityToggle").addEventListener("click", () => {
  document.body.classList.toggle("compact");
});

document.querySelector("#openConfig").addEventListener("click", () => configDialog.showModal());
document.querySelector("#previewConfig").addEventListener("click", () => configDialog.showModal());
document.querySelector("#closeConfig").addEventListener("click", () => configDialog.close());

createRoadmap();
renderLibrary();
selectNode("prd");
