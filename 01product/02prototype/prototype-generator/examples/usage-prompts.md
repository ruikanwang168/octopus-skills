# Usage Prompts

## 1. 生成确认文档

```text
请使用 prototype-generator，根据下面的需求文档生成原型页面索引确认文档。

要求：
1. 先做输入诊断；
2. 判断输入成熟度；
3. 提取功能目录；
4. 生成页面清单；
5. 生成页面关系；
6. 标记推导页面和待确认项；
7. 输出 prototype-index-review.md；
8. 暂时不要生成原型代码。
```

## 2. 根据确认文档生成执行索引

```text
请根据我修改后的 prototype-index-review.md，生成 prototype-index.md。

要求：
1. 将用户已确认的页面转为执行任务；
2. 将用户删除或标记不做的页面排除；
3. 将待补充信息保留在“待补充信息”表中；
4. 每个任务必须包含 Task ID、页面类型、前置页面、触发操作、后续页面、核心组件、是否需要路由、建议文件路径、状态；
5. 所有任务初始状态为 Not Started，除非仍需确认。
```

## 3. 逐页生成原型

```text
请读取 prototype-index.md，选择下一个可以执行的 Not Started 任务。

要求：
1. 本轮只生成一个页面或一个小模块；
2. 不要生成 index 中没有登记的页面；
3. 如需要，生成页面文件、组件、路由、mock 数据；
4. 生成完成后回写 prototype-index.md；
5. 更新 prototype-generation-log.md；
6. 输出下一步建议执行任务。
```

## 4. 完整性检查

```text
请对照需求文档、prototype-index.md 和当前已生成的原型文件，执行完整性检查。

重点检查：
1. 是否遗漏功能模块；
2. 是否遗漏页面；
3. 是否遗漏子页面、弹窗、抽屉；
4. 是否遗漏表格行内操作；
5. 是否遗漏表单提交、取消、校验、反馈；
6. 是否遗漏页面跳转和路由；
7. 是否存在已生成但未登记到 index 的页面；
8. 是否存在 index 标记完成但实际文件缺失的任务；
9. 原型是否可运行或可预览。

请输出 prototype-completeness-check.md。
```

## 5. 继续修复遗漏

```text
请根据 prototype-completeness-check.md 中的补充任务清单，更新 prototype-index.md，并继续逐项修复。
每次只处理一个 Fix Task。
```
