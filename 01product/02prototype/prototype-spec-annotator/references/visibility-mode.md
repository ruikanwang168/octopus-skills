# Visibility Mode

## Contents

- 1. 标记协议
- 2. 删除与显隐的关系
- 3. 显隐脚本
- 4. 组件化项目建议
- 5. 批量删除建议

当用户不是要删除说明，而是要“保留说明但先隐藏”时，按这个文件执行。

适用场景：

- 用户希望页面默认不显示需求说明，需要时再展开
- 用户希望通过批量命令把一整批说明隐藏或重新显示
- 用户希望给每段说明绑定唯一标签，便于后续控制

## 1. 标记协议

以后新增说明区，默认补齐以下标记：

- `data-spec-origin="prototype-spec-annotator"`
- `data-spec-page="<PageId>"`
- `data-spec-id="<UniqueSpecId>"`
- `data-spec-batch="<BatchId>"`
- `data-spec-visible="true"`

同时在注释标记里同步：

```html
<!-- PROTO_SPEC:BEGIN page=AskData id=ask-data-spec batch=2026-04-21-run-01 visible=true source=prototype-spec-annotator -->
...
<!-- PROTO_SPEC:END page=AskData id=ask-data-spec batch=2026-04-21-run-01 visible=true source=prototype-spec-annotator -->
```

推荐含义：

- `page`：页面标识，用于按页面删除或查找
- `id`：单个说明实例的唯一标识
- `batch`：一次批量生成任务的统一批次号
- `visible`：默认显隐状态

默认命名约定：

- 未指定 `spec-id` 时，默认使用 `{pageId}-spec`
- 未指定 `batch-id` 时，默认使用 `spec-batch-YYYYMMDD-HHMMSS`

## 2. 删除与显隐的关系

- 删除：说明区从源文件中被移除
- 隐藏：说明区仍保留在源文件和 DOM 中，但默认不显示

如果用户还不确定是否彻底移除，优先隐藏而不是删除。

## 3. 显隐脚本

脚本位置：

- [scripts/toggle_specs.py](../scripts/toggle_specs.py)

能力范围：

- 对带标准属性的 inline 说明块执行 `show` / `hide`
- 支持按 `page-id`、`spec-id`、`batch-id` 或整项目批量切换
- 隐藏通过 `data-spec-visible="false"` + `hidden` 完成

常用命令：

```bash
python3 prototype-spec-annotator/scripts/toggle_specs.py --root /path/to/project --all --hide
python3 prototype-spec-annotator/scripts/toggle_specs.py --root /path/to/project --all --show
python3 prototype-spec-annotator/scripts/toggle_specs.py --root /path/to/project --page-ids AskData --hide
python3 prototype-spec-annotator/scripts/toggle_specs.py --root /path/to/project --spec-ids ask-data-spec --show
python3 prototype-spec-annotator/scripts/toggle_specs.py --root /path/to/project --batch-id 2026-04-21-run-01 --hide --dry-run
```

参数说明：

- `--all`：全量显隐
- `--page-ids`：按页面显隐
- `--spec-ids`：按唯一说明实例显隐
- `--batch-id`：按批次显隐
- `--files`：只处理指定文件
- `--hide`：隐藏
- `--show`：显示
- `--dry-run`：预览不写回

## 4. 组件化项目建议

如果项目采用 `withPageSpec` / `PageSpecDoc` 这种共享组件模式：

- 全局显隐可以通过组件级开关控制
- 单页显隐应在组件层引入 `visible` 状态或 page-key 级配置
- 不建议只靠删除脚本模拟“隐藏”，因为删除是不可逆的代码改写

推荐做法：

- `PageSpecDoc` 增加 `visible?: boolean` 或内部折叠状态
- 标题区保留一个显隐切换按钮
- 切换只控制说明区内容，不影响原型主页面布局
- 具体实现优先参考 [react-shared-component-mode.md](react-shared-component-mode.md)

注意：

- 如果是运行时按钮显隐，不要把整个说明区根节点一起 `hidden`，否则用户看不到展开按钮
- 运行时显隐更适合“壳层常驻，正文折叠”
- `hidden` 更适合源码级默认隐藏或脚本级批量隐藏

## 5. 批量删除建议

如果用户明确要求“一键批量删除”，优先使用：

- [cleanup-mode.md](cleanup-mode.md) 中的 `clear_specs.py`

如果用户明确要求“保留说明，只是暂时不显示”，优先使用：

- 本文件中的 `toggle_specs.py`
