# 原型标注说明

本目录由 `prototype-annotator` skill 生成，用于保存原型页面的标注数据和运行时资源。

## 目录说明

- `annotations.json`：标注数据源。AI 生成和页面内手动编辑后的标注最终都应写入这里。
- `assets/`：标注正文引用的图片资产，例如从剪贴板粘贴的截图。
- `page-map.json`：原型扫描结果，用于重新生成标注或校验 selector。
- `history.jsonl`：本地在线评审服务写入的编辑历史。
- `runtime/`：标注层所需的 JavaScript 和 CSS 运行时资源。

## 如何启动在线标注

请在 `prototype-annotator` skill 项目目录中运行本地评审服务，并把当前原型路径作为参数传入。下面命令里的路径均为占位示例，请替换为你本机的实际目录：

```bash
cd /path/to/prototype-annotator
python3 scripts/serve_annotation_review.py /path/to/your/prototype
```

如果不想切换目录，也可以直接使用脚本绝对路径：

```bash
python3 /path/to/prototype-annotator/scripts/serve_annotation_review.py /path/to/your/prototype
```

启动后终端会输出类似地址：

```text
Serving annotation review at http://127.0.0.1:8765/
```

在浏览器中打开该地址即可在线查看、编辑、新增、删除和导出标注。页面内保存的修改会通过本地评审服务回写到本目录的 `annotations.json`。

## 注意事项

- 不建议用普通静态服务（例如 `python3 -m http.server`）进行人工编辑，因为它不能处理回写请求；页面修改只能暂存在浏览器 `localStorage` 草稿中。
- 静态 HTML 中内嵌的标注 JSON 只是离线或读取失败时的兜底快照，正式数据源仍是本目录的 `annotations.json`。
- 如果更新了 skill 的运行时修复，需要重新执行注入命令，或刷新本目录 `runtime/` 下的运行时文件。
- 如需清空或删除标注结果，请运行 `python3 /path/to/prototype-annotator/scripts/clear_annotations.py /path/to/your/prototype`。该命令会移除标注数据和静态 HTML 注入块，但不会删除 React/Vue adapter 源码，以免破坏原型构建。
