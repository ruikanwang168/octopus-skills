# Cleanup Mode

## Contents

- 1. 先区分删除范围
- 2. 新增说明时必须留下可回收标记
- 3. 清理脚本
- 4. 清理模式下的执行要求
- 5. 兼容旧版本说明块的判断锚点

当用户不是要“补需求说明”，而是要“清空需求说明”时，按这个文件执行。

适用场景：

- 一键清空当前项目里由 `prototype-spec-annotator` 添加的全部需求说明
- 只清空指定页面的需求说明
- 先 dry run 预览，再真正删除
- 兼容旧版本已插入的说明块，不要求目标项目先升级到新标记格式

## 1. 先区分删除范围

优先级如下：

1. 用户明确给文件路径：只清理这些文件
2. 用户明确给页面标识：只清理这些页面对应的说明
3. 用户明确要求“一键清空全部”：对目标根目录执行全量清理

安全边界：

- 清理目标只允许是说明区、说明包装器、说明 helper、说明 wrapper export
- 不要删除原型页面本身的业务模块、表格、表单、图表、导航
- 如果无法稳定判断某一段是否属于说明区，默认保留

## 2. 新增说明时必须留下可回收标记

以后凡是直接把说明区写回 HTML / JSX / Vue / JS 文件，默认都要留下两层可回收信息：

- 外层注释标记：`PROTO_SPEC:BEGIN` / `PROTO_SPEC:END`
- 根节点属性：`data-spec-origin="prototype-spec-annotator"`、`data-spec-page="<PageId>"`、`data-spec-id="<UniqueSpecId>"`、`data-spec-batch="<BatchId>"`

HTML / Vue 示例：

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

JSX / TSX 示例：

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

如果项目已经采用 `withPageSpec("PageKey", Component)` 或 `<PageSpecDoc />` 模式：

- 优先沿用现有模式，不要强行改回纯 HTML 插入
- 页面 key 必须稳定，后续按页面清理时就用这个 key
- 如果可以修改 `PageSpecDoc` 根节点，补 `data-spec-origin` 和 `data-spec-page`

## 3. 清理脚本

脚本位置：

- [scripts/clear_specs.py](../scripts/clear_specs.py)

默认能力：

- 优先删除显式标记包裹的说明块
- 兼容删除 `withPageSpec("PageKey", Component)` 导出的页面包装
- 兼容删除 `<PageSpecDoc ... />` 标签与相关 import
- 兼容删除旧版 `data-role="page-spec"`、`data-module="spec-section"`、`proto-spec-doc` 说明块
- 兼容删除旧版 `renderXxxSpecSection()` 这类说明 helper

常用命令：

```bash
python3 prototype-spec-annotator/scripts/clear_specs.py --root /path/to/project --all
python3 prototype-spec-annotator/scripts/clear_specs.py --root /path/to/project --page-ids AppManagement AskData
python3 prototype-spec-annotator/scripts/clear_specs.py --root /path/to/project --spec-ids ask-data-spec app-management-spec
python3 prototype-spec-annotator/scripts/clear_specs.py --root /path/to/project --batch-id 2026-04-21-run-01
python3 prototype-spec-annotator/scripts/clear_specs.py --root /path/to/project --files src/pages/app.tsx CRM/工作台.html
python3 prototype-spec-annotator/scripts/clear_specs.py --root /path/to/project --page-ids AppManagement --dry-run
```

参数约定：

- `--root`：项目根目录，用于解析相对路径
- `--all`：清空根目录下所有可识别说明
- `--page-ids`：按页面标识清空；可匹配标记里的 `page=`、`data-spec-page`、`withPageSpec` 的 page key，以及文件名 / 路径中的页面标识
- `--spec-ids`：按说明实例唯一标识清空；适用于已经写入 `data-spec-id` 或注释 `id=...` 的说明块
- `--batch-id`：按批次号清空；适用于一次批量生成的一整批说明
- `--files`：只处理指定文件或目录
- `--dry-run`：只预览改动，不写回文件

## 4. 清理模式下的执行要求

- 先 dry run 再决定是否正式写回，除非用户明确要求直接清
- 删除后要复查页面主体是否仍可渲染，尤其是 React 默认导出和 import 是否恢复正确
- 删除后不要顺手重排业务布局、替换页面样式或重命名业务 DOM
- 如果目标项目里同时存在业务自带的“帮助说明区”和 skill 插入的“需求说明区”，只删后者

## 5. 兼容旧版本说明块的判断锚点

以下命中任一时，可视为旧版说明锚点：

- `data-role="page-spec"`
- `data-module="spec-section"`
- `class` / `className` 包含 `proto-spec-doc`
- `data-spec-id="<UniqueSpecId>"`
- `data-spec-batch="<BatchId>"`
- `withPageSpec("PageKey", Component)`
- `<PageSpecDoc ... />`
- `renderXxxSpecSection()` 且函数体里明显返回说明区 DOM

但要注意：

- 业务页面中若恰好存在普通 `section`，不能只因为它叫 `section` 就删除
- 业务页面中若存在真正的“产品帮助区”，且不带上述锚点，默认不要误删
