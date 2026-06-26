# design-generator

`design-generator` 是一个用于生成可执行设计系统包的 Codex 技能。它会根据本地源码、截图、URL 抓取结果或产品说明，沉淀一套可被后续 AI 编程工具直接使用的设计规范。

产物不是情绪板，也不是通用后台模板，而是一套带证据边界、生成约束和可视化预览的设计系统文件包。

## 产出内容

默认生成一个 `DESIGN` 目录，包含：

```text
DESIGN/
  DESIGN.md          # 设计系统源文件，包含 YAML 前置信息和 10 个说明章节
  preview.html       # 主运行态 / 亮色预览
  preview-dark.html  # 暗色模式或暗色检查视图
  example.html       # 基于 DESIGN.md 生成的代表性页面样例
  DESIGN_GAPS.md     # 待确认项、冲突项、低置信度判断记录
```

`DESIGN.md` 是单一事实源。`DESIGN_GAPS.md` 只记录待确认内容，不能替代 `DESIGN.md` 中的当前默认决策。

## 适用输入

技能会先判断证据模式，再按不同策略生成设计系统：

- `source+screenshot`：源码 + 截图或运行态页面，优先级最高。
- `source-only`：只有本地项目源码。
- `screenshot-only`：只有截图，颜色、间距、字号等应标记为近似或推断。
- `url`：在线 URL、本地开发 URL 或捕获的页面数据。
- `brief`：只有产品概念、功能说明或需求文档，需要先确认视觉方向。

证据优先级通常是：

```text
用户明确要求
> 运行态 DOM / 计算样式 / CSS 变量
> 源码中的启用 token 和组件实现
> 截图中的可见结构、密度和状态
> theme-data 候选统计
> 保守的产品默认值
```

## 标准流程

1. 阅读 `SKILL.md`，确认输入模式和输出语言。
2. 按输入类型阅读 `references/input-analysis.md`。
3. 写产物前阅读 `references/output-contract.md`。
4. 必要时参考 `references/design-md-corpus.md` 选择界面原型类型。
5. 生成脚手架。
6. 填完整 `DESIGN.md` 的统一 front matter 和 10 个章节。
7. 从 `DESIGN.md` 渲染预览文件。
8. 手写或完善 `example.html`，证明设计规范能指导页面生成。
9. 生成 `DESIGN_GAPS.md`。
10. 运行校验脚本并修复硬错误。

## 常用命令

生成设计系统目录：

```bash
python3 scripts/scaffold_design_folder.py \
  --project-root /absolute/path/to/project \
  --name "产品名称" \
  --markdown-name DESIGN.md \
  --format ai-design-system-v3
```

如果用户指定了输出目录：

```bash
python3 scripts/scaffold_design_folder.py \
  --output /absolute/path/to/output/DESIGN \
  --name "产品名称" \
  --language zh-CN
```

从 `DESIGN.md` 渲染预览：

```bash
python3 scripts/render_preview_from_design_md.py \
  /absolute/path/to/DESIGN \
  --markdown-name DESIGN.md
```

生成待确认项文档：

```bash
python3 scripts/generate_gaps_doc.py \
  /absolute/path/to/DESIGN \
  --markdown-name DESIGN.md \
  --language zh
```

校验设计系统包：

```bash
python3 scripts/validate_design_folder.py \
  /absolute/path/to/DESIGN \
  --markdown-name DESIGN.md \
  --format ai-design-system-v3
```

如果用户提供了 `theme-data/` URL 捕获目录，可先提取候选证据：

```bash
python3 scripts/extract_url_theme_evidence.py /absolute/path/to/theme-data
```

该输出只作为内部候选证据使用，默认不放进最终五件套。

## 目录结构

```text
.
  SKILL.md
  assets/
    DESIGN.template.md
    DESIGN_GAPS.template.md
    preview.template.html
    preview-dark.template.html
    example.template.html
  references/
    input-analysis.md
    output-contract.md
    design-md-corpus.md
    front-matter-dedup-rules.md
  scripts/
    scaffold_design_folder.py
    render_preview_from_design_md.py
    generate_gaps_doc.py
    validate_design_folder.py
    extract_url_theme_evidence.py
    front_matter_schema.py
```

## 关键约束

- 新产物使用 `ai-design-system-v3` 统一结构。
- `DESIGN.md` 必须包含统一 YAML 前置信息和 10 个章节。
- 不要在多个字段重复写同一个设计事实；颜色、字体、间距等只权威存于 `tokens.*`。
- `components`、`layout`、`pageTemplates`、`generationRules` 应引用 token，而不是重新写一套字面量。
- 不允许留下 `unknown`、`unavailable`、`TODO`、`MUST_REPLACE` 等不可执行占位内容。
- 证据不足时，要写入保守推荐值，并在 `evidence.decisions` 中标记 `recommended-default` 或 `inferred` 及理由。
- `example.html` 是 Agent 根据 `DESIGN.md` 生成的验证样例，不应把一次性的样例请求写回 `DESIGN.md`。

## 维护提示

- `front_matter_schema.py` 会把 v3 结构投影成旧渲染器可读路径，便于兼容历史模板。
- `validate_design_folder.py` 是输出质量守门脚本，修改 schema 或模板后应同步更新校验规则。
- `render_preview_from_design_md.py` 负责从同一份 `DESIGN.md` 派生预览，避免手写第二套设计语言。
- `generate_gaps_doc.py` 会从 `openQuestions`、`knownLimits`、`assumptions`、`legacyTokens` 和低置信度决策生成确认清单。
