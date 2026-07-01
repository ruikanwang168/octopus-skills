# 页面交互视觉伴侣指南

本指南说明 page-interaction-designer 如何用浏览器展示可点击的页面交互方案。

## 核心原则

页面交互设计阶段默认使用视觉方案确认。目标不是做高保真视觉稿，而是让用户直观看到：

- 页面区域如何组织
- 用户从哪里进入、点哪里、去哪里
- 弹窗、抽屉、详情面板、配置页如何出现
- 状态、分支、回环、异常如何表达

不要在这里设计配色、品牌风格、插画或最终 UI 细节。

## 启动

```bash
scripts/start-server.sh --project-dir /path/to/project --open
```

记录返回的 `url`、`screen_dir`、`state_dir`。

向用户说明：浏览器里会展示页面交互方案，可以点击选择；他们也可以在终端补充意见。

## 写页面

默认向 `screen_dir` 写 HTML 片段。不要写完整 HTML，除非需要完全控制页面。

文件名要语义化且不重复：

- `page-scope.html`
- `home-layout.html`
- `home-layout-v2.html`
- `detail-panel.html`
- `form-flow.html`
- `state-model.html`

每屏最多 2-3 个方案，复杂时最多 4 个。

## 推荐屏幕类型

### 页面清单确认

展示所有页面、入口和关系，让用户确认是否遗漏。

### 布局方案选择

用卡片展示 2-3 个布局：

- 左导航 + 主区域 + 右详情
- 顶部阶段导航 + 中央流程图
- 阶段看板 + 节点详情抽屉

### 复杂流程确认

用流程图或分步结构展示：

- 创建/编辑/发布流程
- 条件分支
- 回到上游节点
- 审批/确认/失败重试

### 状态模型确认

并排展示：

- 默认状态
- 加载中
- 空状态
- 错误状态
- 无权限
- 保存成功/失败

## 读取反馈

用户点击会记录到：

```text
$STATE_DIR/events
```

事件是 JSON lines：

```jsonl
{"type":"click","choice":"stage-first","text":"阶段分栏 ...","timestamp":1706000101}
```

读取事件后，结合用户终端回复判断：

- 最后一次点击通常是最终选择
- 连续点击多个方案说明用户可能犹豫
- 用户文字反馈优先级高于点击事件

优先用等待脚本减少用户来回切换：

```bash
scripts/wait-for-choice.sh "$STATE_DIR" --timeout-seconds 900 --settle-seconds 1
```

脚本输出最新事件后，直接根据 `choice` 或 `value` 继续下一步。只有在等待超时、环境不支持长时间运行命令，或需要用户补充文字原因时，才让用户回到 AI 聊天窗口。

## 回到终端

当下一步不需要浏览器时，推送等待页：

```html
<div style="display:flex;align-items:center;justify-content:center;min-height:60vh">
  <p class="subtitle">接下来在终端继续确认...</p>
</div>
```

## 输出沉淀

每次用户确认一个视觉方案后，立即记录成页面交互细节草稿：

- 选择了哪个方案
- 为什么适合
- 页面结构
- 用户操作路径
- 状态与反馈
- 仍待确认的问题

最终汇总到页面交互细节文档。
