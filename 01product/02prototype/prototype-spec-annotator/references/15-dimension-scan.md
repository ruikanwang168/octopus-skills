# 15-Dimension Evidence Scan

Use this as a coverage scan before writing or reviewing Markdown page specs. Do not force every page to output all 15 dimensions. Output only dimensions that are visible in the prototype, directly inferable from UI structure, or explicitly provided by the user.

## Output Rule

- Keep the normal page-spec structure from `markdown-spec-format.md`.
- Map detected dimensions into the relevant module sections, such as `【筛选条件】交互规则说明`, `【结果区】显示规则说明`, `【字段输入规则】说明`, or `【功能操作】交互规则说明`.
- If the user explicitly asks for PRD-style output, dimension headings may be used.
- If a dimension is important but not visible, write a short `待补充` item only when the user asked for gaps or risks. Otherwise skip it.
- Never invent backend rules, permission matrices, notifications, audit logs, data storage rules, or third-party integrations from UI alone.

## The 15 Dimensions

1. **页面与组件显隐规则**：常驻元素、触发显示的弹窗/抽屉/气泡/按钮、关闭条件、返回路径。
2. **列表与表格展现规则**：数据加载、默认排序、分页/触底加载、自定义列、冻结列、筛选联动、空状态。
3. **缺省与异常兜底规范**：无数据、搜索无结果、加载失败、网络异常、无权限、CTA。
4. **全局组件交互规范**：日期选择器、级联选择、穿梭框、上传、富文本、地图、图表等复用组件；只写本页特殊约束，不重复基础通用规范。
5. **表单输入与校验规则**：字段名、组件类型、必填、默认值、placeholder、长度限制、焦点行为、校验时机、错误提示。
6. **功能操作交互规则**：新增、编辑、删除、发布、停用、导入导出等按钮的可用条件、点击响应、确认文案、成功/失败反馈。
7. **格式与安全防刷规则**：手机号、邮箱、密码、验证码、人机验证、倒计时、连续错误限制；仅在登录/注册/安全入口或页面可见时输出。
8. **数据提交与保存规则**：提交前全局校验、保存/提交 API 触发可见线索、成功后关闭/刷新/跳转、失败提示；不要从 UI 编造落库表结构。
9. **业务状态流转规则**：状态标签、状态来源、按钮对状态的影响、状态变更触发节点、重置条件。
10. **特殊业务机制说明**：上传、下载、导入、导出、模板下载、字段映射、文件名规则、硬件能力调用。
11. **权限控制与可见性规则**：按钮级权限、数据范围、敏感字段脱敏、游客/登录/VIP 差异；仅在可见或用户补充时输出。
12. **系统消息与通知规则**：站内信、邮件、短信、Push 的触发条件和变量文案；仅在页面包含通知配置或用户补充时输出。
13. **系统操作日志与审计规范**：高危操作留痕、操作人、时间、IP、对象名称；C 端可转化为埋点事件；仅在可见或用户补充时输出。
14. **第三方服务与接口集成约束**：支付、登录 SDK、短信网关、企查查、地图、AI/模型服务等系统边界；只划边界，不编写未给出的接口细节。
15. **项目元数据与阅读指引**：版本、更新日志、背景说明、AI 生成说明、阅读范围、页面来源。

## Shape Mapping

- **移动端 / C 端**：dimension 2 focuses on pull-to-refresh, infinite scroll, skeleton loading; dimension 10 may include camera, album, GPS, Bluetooth, biometric auth; dimension 11 includes guest/login/member visibility; dimension 13 includes tracking events.
- **AIGC / AI-native**：dimension 5 includes prompt limits, voice input, attachments; dimension 9 includes `等待输入 -> 生成中 -> 生成完成/失败 -> 重新生成`; dimension 10 includes file parsing and generated asset export; dimension 14 includes model/provider boundary if visible.
- **B端 / SaaS**：dimension 2, 5, 6, 8, 9, 10, 11 are usually high-value, but permission, notification, audit, and integrations still require page evidence or user context.

## Coverage Note Template

Use this only when the user asks for a gap/risk review:

```markdown
## 待补充维度

- 【权限控制与可见性规则】：页面未展示角色、组织或按钮权限差异，需业务侧补充。
- 【系统消息与通知规则】：页面未展示通知配置或消息入口，暂不推断通知触发。
```
