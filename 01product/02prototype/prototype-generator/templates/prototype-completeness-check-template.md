# Prototype Completeness Check

> 文件名建议：`prototype-completeness-check.md`  
> 用途：在原型生成完成后，对照需求文档和 `prototype-index.md` 检查是否遗漏页面、交互、路由和文件。

---

## 1. 检查结论

| 项目 | 结果 |
|---|---|
| 是否完成所有已确认任务 | 是 / 否 |
| 是否存在未完成任务 | 是 / 否 |
| 是否存在待确认任务 | 是 / 否 |
| 是否存在缺失页面 | 是 / 否 |
| 是否存在缺失交互 | 是 / 否 |
| 是否存在缺失路由 | 是 / 否 |
| 是否存在未登记页面 | 是 / 否 |
| 原型是否可运行 / 可预览 | 是 / 否 / 未验证 |
| 工作区模式 | standalone / prototype-starter-compatible |
| 是否生成 feature-manifest.json | 是 / 否 / 不适用 |
| 是否通过 starter compliance | 是 / 否 / 未运行 / 不适用 |
| 是否建议进入补充生成 | 是 / 否 |

### 总体说明

> 

---

## 2. 功能模块覆盖检查

| 功能模块 | 需求文档是否提及 | Index 是否覆盖 | 原型是否生成 | 检查结果 |
|---|---|---|---|---|
|  | 是 / 否 | 是 / 否 | 是 / 否 | 已覆盖 / 缺失 / 待确认 |

---

## 3. 页面覆盖检查

| 页面名称 | 页面类型 | 来源 | Index 状态 | 是否有对应文件 | 是否有路由 / 入口 | 检查结果 |
|---|---|---|---|---|---|---|
|  |  | Explicit / Inferred / Needs Confirmation |  | 是 / 否 | 是 / 否 | 已覆盖 / 缺失 / 待确认 |

---

## 4. 页面关系检查

| 前置页面 | 触发操作 | 目标页面 | 路由 / 交互是否实现 | 检查结果 |
|---|---|---|---|---|
|  |  |  | 是 / 否 |  |

---

## 5. 交互完整性检查

| 页面 | 交互项 | 是否需要 | 是否实现 | 检查结果 |
|---|---|---|---|---|
|  | 搜索 / 筛选 / 新建 / 编辑 / 删除 / 查看详情 / 导入 / 导出 / 提交 / 取消 / 保存 | 是 / 否 | 是 / 否 |  |

---

## 6. 表单状态检查

| 页面 | 状态 / 规则 | 是否实现 | 检查结果 |
|---|---|---|---|
|  | 默认值 / 必填校验 / 提交成功 / 提交失败 / 取消返回 / 保存草稿 | 是 / 否 |  |

---

## 7. 表格操作检查

| 页面 | 表格操作 | 是否实现 | 检查结果 |
|---|---|---|---|
|  | 行内查看 / 行内编辑 / 行内删除 / 批量删除 / 导入 / 导出 | 是 / 否 |  |

---

## 8. 文件与路由检查

| Task ID | Page Name | Expected File | Actual File | Expected Route / Entry | Actual Route / Entry | Check Result |
|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |

---

## 9. Manifest 与 Starter 兼容性检查

> 仅在 prototype-starter-compatible 模式下必填。standalone 模式填写“不适用”。

| 检查项 | 期望 | 实际 | 检查结果 |
|---|---|---|---|
| 已确认任务是否进入 manifest | `prototype-index.md` 中已确认且无阻塞的页面/场景应进入 `feature-manifest.json` |  | 已通过 / 缺失 / 不适用 |
| 阻塞任务是否排除 manifest | `Needs Confirmation` / `Needs Input` 不应进入 manifest，除非用户选择 draft |  | 已通过 / 异常 / 不适用 |
| 页面是否由 starter 骨架生成 | 可用时应使用 `node scripts/new-feature.cjs --manifest` |  | 已通过 / 未使用 / 不适用 |
| 页面是否引用 shared CSS/JS | 页面应复用 starter 的共享资源 |  | 已通过 / 缺失 / 不适用 |
| 页面是否有稳定元数据 | `data-page-key`、`data-page-kind`、`data-surface` 等应存在 |  | 已通过 / 缺失 / 不适用 |
| 页面是否携带设计源信息 | `data-design-source-sha` 和 `data-design-contract-version` 应存在 |  | 已通过 / 缺失 / 不适用 |
| 是否运行 compliance | 应运行 `node scripts/check-prototype-compliance.cjs` |  | 已通过 / 未运行 / 不适用 |

---

## 10. 未登记页面检查

| Actual File / Route | 是否在 prototype-index.md | 是否在 feature-manifest.json | 是否允许存在 | 处理建议 |
|---|---|---|---|---|
|  | 是 / 否 | 是 / 否 / 不适用 | 是 / 否 | 删除 / 补登记 / 保留并说明 |

---

## 11. 发现的问题

| 问题ID | 问题类型 | 问题描述 | 影响范围 | 建议处理 |
|---|---|---|---|---|
| BUG001 | 缺失页面 / 缺失交互 / 路由缺失 / 状态缺失 / 文件缺失 / Index 不一致 / Manifest 不一致 / Starter 合规失败 / 无法运行 |  |  |  |

---

## 12. 补充任务清单

| Fix Task ID | 缺失内容 | 来源 | 建议动作 | 优先级 | 状态 |
|---|---|---|---|---|---|
| FIX001 |  | 完整性检查发现 | 新增页面 / 补充交互 / 修复路由 / 更新 index | 高 / 中 / 低 | Not Started |
