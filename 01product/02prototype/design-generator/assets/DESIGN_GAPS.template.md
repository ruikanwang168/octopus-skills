# DESIGN_GAPS.md｜设计待确认项与冲突清单

本文件记录 design-generator 在分析产品源码、截图、URL 或产品描述时发现的不确定项、冲突项、缺失项和低置信度判断。

这些内容不会直接作为 AI 生成页面的主规则。AI 生成页面时应以 `DESIGN.md` 为准。

当人工确认本文件中的问题后，应将确认结果回写到 `DESIGN.md`，并重新生成 `preview.html`。

> **生成时间**：{generation_time}
> **证据模式**：{evidence_mode}
> **置信度**：{confidence}

---

## 1. 总体置信度摘要

| 维度 | 置信度 | 说明 |
|---|---|---|
| 产品类型 | {confidence_product_type} | {notes_product_type} |
| 主色 | {confidence_primary_color} | {notes_primary_color} |
| 字体 | {confidence_typography} | {notes_typography} |
| 布局 | {confidence_layout} | {notes_layout} |
| 组件体系 | {confidence_components} | {notes_components} |
| 页面模板 | {confidence_page_templates} | {notes_page_templates} |
| 暗色模式 | {confidence_dark_mode} | {notes_dark_mode} |
| 移动端 | {confidence_mobile} | {notes_mobile} |

---

## 2. 高优先级待确认项

高优先级指会直接影响 AI 生成页面准确性的内容。

| ID | 类型 | 待确认问题 | 当前判断 | 证据来源 | 置信度 | 影响范围 | 当前处理策略 | 需要确认 | 回写位置 |
|---|---|---|---|---|---|---|---|---|---|
| AUTO-GENERATED | 未确认 | 运行 `scripts/generate_gaps_doc.py` 后填充真实问题 | 当前模板不代表真实判断 | scaffold template | 待生成 | 待生成 | 完成 DESIGN.md 后运行脚本 | 待生成 | DESIGN.md / DESIGN_GAPS.md |

---

## 3. 中优先级待确认项

中优先级指影响局部组件或部分页面，但不影响整体生成。

| ID | 类型 | 待确认问题 | 当前判断 | 证据来源 | 置信度 | 影响范围 | 当前处理策略 | 需要确认 | 回写位置 |
|---|---|---|---|---|---|---|---|---|---|
| AUTO-GENERATED | 未确认 | 运行 `scripts/generate_gaps_doc.py` 后填充真实问题 | 当前模板不代表真实判断 | scaffold template | 待生成 | 待生成 | 完成 DESIGN.md 后运行脚本 | 待生成 | DESIGN.md / DESIGN_GAPS.md |

---

## 4. 低优先级待确认项

低优先级指不会明显影响 AI 生成页面，但可后续完善。

| ID | 类型 | 待确认问题 | 当前判断 | 证据来源 | 置信度 | 影响范围 | 当前处理策略 | 需要确认 | 回写位置 |
|---|---|---|---|---|---|---|---|---|---|
| AUTO-GENERATED | 未确认 | 运行 `scripts/generate_gaps_doc.py` 后填充真实问题 | 当前模板不代表真实判断 | scaffold template | 待生成 | 待生成 | 完成 DESIGN.md 后运行脚本 | 待生成 | DESIGN.md / DESIGN_GAPS.md |

---

## 5. 设计冲突清单

冲突项必须展示候选值、当前采用值和采用原因。

| ID | 冲突项 | 候选值 / 证据 | 当前采用 | 原因 | 是否需要确认 |
|---|---|---|---|---|---|
| AUTO-GENERATED | 运行 `scripts/generate_gaps_doc.py` 后填充 | — | — | — | — |

---

## 6. 未覆盖 / 未观察到的内容

以下内容在当前输入中未观察到，默认不会作为 DESIGN.md 的主规则：

| 类别 | 状态 | 默认处理 |
|---|---|---|
| 暗色模式 | 未确认 | 不默认生成暗色主题页面 |
| 移动端 APP | 未确认 | 不默认生成移动端页面 |
| 数据大屏 | 未确认 | 不默认生成大屏风格 |
| 国际化 i18n | 未确认 | 不默认生成多语言切换 |
| 可访问性规范 | 证据不足 | 仅按常规 focus / disabled 处理 |
| 图表色板 | 未完整观察 | 不主动扩展图表色板 |

---

## 7. 人工确认记录

用于后续迭代闭环。

| ID | 确认项 | 确认结论 | 确认人 / 来源 | 确认时间 | 是否已回写 DESIGN.md |
|---|---|---|---|---|---|
| AUTO-GENERATED | 人工确认后填充 | — | — | — | — |

---

## 确认流程

1. 逐项确认上述待确认项
2. 提供反馈（如「侧栏宽度确认是 240px」）
3. AI 会自动更新 DESIGN.md
4. AI 会更新本文档（将已确认项移到「人工确认记录」）
5. 重新生成 preview.html
