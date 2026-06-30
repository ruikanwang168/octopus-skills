# AI_IGNORE.md 生成规则

## 文件职责

`AI_IGNORE.md` 是 AI 扫描忽略规则文件，用来声明 AI 在项目分析、规则生成、规则更新、项目总结和源码检索时默认跳过的路径、文件和匹配模式。

这个文件属于用户维护范围，不属于 `airule-init` 的增量更新范围。

## 匹配规则

`AI_IGNORE.md` 中每一行按仓库根目录相对路径解释：

- 空行和 `#` 开头的行作为注释。
- 目录以 `/` 结尾，例如 `node_modules/`。
- 文件或 glob 使用常见通配格式，例如 `*.log`、`dist/**`。
- 正则匹配使用 `regex:` 前缀，例如 `regex:^tmp/.*\.json$`。
- 允许读取的例外使用 `!` 前缀，例如 `!.env.example`、`!regex:^docs/examples/.*$`。

## 默认模板

仅当目标项目缺少 `AI_IGNORE.md` 时，初始化模式或更新模式创建下面的默认忽略模板：

````md
# AI 忽略规则

本文件由项目维护者手动维护，用于声明 AI 在扫描、总结、生成或更新规则时默认跳过的文件、目录和匹配模式。

`airule-init` 初始化时只创建本文件；后续增量更新不会自动修改或覆盖这里的内容。

## 写法

- 目录：`node_modules/`
- 文件或 glob：`*.log`、`dist/**`
- 正则：`regex:^tmp/.*\.json$`
- 允许读取例外：`!.env.example`

## 忽略列表

```gitignore
# 版本控制
.git/
.svn/
.hg/

# 依赖与缓存
node_modules/
vendor/
.venv/
venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.cache/

# 构建产物与覆盖率
dist/
build/
out/
target/
coverage/
.next/
.nuxt/
.turbo/

# 日志与临时文件
*.log
logs/
tmp/
temp/

# 本地环境与敏感信息
.env
.env.*
*.pem
*.key
*.p12
*.secret*
secrets/

# 允许读取的模板或非敏感示例
!.env.example
!.env.template
```
````

## 生成规则

- 只在文件不存在时创建。
- 如果文件已存在，无论内容是否为空，更新模式都不自动修改。
- 创建后，后续项目扫描、`PROJECT.md` 生成和增量更新都必须遵守此文件。
- 可以读取该文件来确定扫描边界，但不能把它当作待同步文件改写。
- 只有用户明确说“修改 AI_IGNORE.md”“更新忽略列表”或“把这个路径加入忽略”时，才允许更新。

## 执行规则

- 深度检索源码前，必须先读取 `AI_IGNORE.md`；如果文件缺失，先按默认模板创建，或在未写入前临时采用默认忽略列表。
- 被忽略路径不得用于项目概述、技术栈、目录规约、代码风格或依赖判断。
- 如果任务确实需要读取被忽略文件，必须先说明原因；涉及密钥、令牌、私钥、生产凭据时，即使用户要求也只做结构性说明，不输出敏感值。
- 允许读取例外只表示可以分析，不表示必须读取；仍按任务相关性最小化读取。
