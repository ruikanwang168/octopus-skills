from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_POINTS = [
    "名词解释",
    "业务背景",
    "业务痛点",
    "涉及角色",
    "解决方案",
    "实现边界",
    "核心流程",
    "功能清单",
    "业务实体",
    "业务状态",
    "数据权限",
    "异常兜底",
    "外部依赖",
    "老数据兼容",
    "非功能指标",
    "审计可观测",
]


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.exists():
        raise AssertionError(f"missing required file: {relative}")
    return path.read_text(encoding="utf-8")


def require(text: str, pattern: str, label: str) -> None:
    if not re.search(pattern, text, re.MULTILINE):
        raise AssertionError(f"missing {label}: {pattern}")


def main() -> int:
    skill = read("SKILL.md")
    framework = read("references/analysis-framework.md")
    template = read("references/document-template.md")
    readme = read("README.md")
    metadata = read("agents/openai.yaml")

    require(
        skill,
        r"(?m)^description:\s*\|\n\s+Use when",
        "trigger-focused description",
    )
    for point in EXPECTED_POINTS:
        if point not in framework or point not in template:
            raise AssertionError(f"16-point coverage missing: {point}")

    for layer_heading in [
        "## 一、认知层",
        "## 二、边界层",
        "## 三、交付层",
        "## 四、防御层",
    ]:
        if re.search(rf"(?m)^{re.escape(layer_heading)}$", template):
            raise AssertionError(
                f"delivery template must not expose internal layer heading: {layer_heading}"
            )

    for point in EXPECTED_POINTS:
        require(
            template,
            rf"(?m)^## {re.escape(point)}$",
            f"unnumbered reference heading {point}",
        )

    fixed_heading_pattern = (
        rf"(?m)^## \d+\. ({'|'.join(re.escape(point) for point in EXPECTED_POINTS)})$"
    )
    if re.search(fixed_heading_pattern, template):
        raise AssertionError(
            "delivery reference must not expose fixed point numbers as output headings"
        )

    numbering_rules = skill + template + readme
    for phrase in [
        "先删除不适用章节",
        "从 1 开始连续重新编号",
        "不允许跳号",
        "显示编号只表示文档阅读顺序",
    ]:
        if phrase not in numbering_rules:
            raise AssertionError(f"continuous numbering rule missing: {phrase}")

    if re.search(r"(?<!不)允许跳号", numbering_rules):
        raise AssertionError("obsolete fixed numbering rule remains: 允许跳号")
    if "保留原编号" in numbering_rules:
        raise AssertionError("obsolete fixed numbering rule remains: 保留原编号")

    for phrase in [
        "每轮只问 2 到 4 个问题",
        "表面诉求",
        "必要性检验",
        "不按 16 个考量点逐项提问",
        "references/analysis-framework.md",
        "references/document-template.md",
    ]:
        if phrase not in skill:
            raise AssertionError(f"conversation guard missing: {phrase}")

    concision_rules = skill + template
    for phrase in [
        "最少文字表达完整业务结论",
        "篇幅不设目标",
        "跨章节重复",
        "同一事实只在最合适的章节完整表达一次",
        "精简不得删掉",
    ]:
        if phrase not in concision_rules:
            raise AssertionError(f"concise delivery rule missing: {phrase}")

    terminology_rules = skill + framework + template
    for phrase in [
        "名词解释采用准入制",
        "核心业务领域",
        "关键业务对象、规则、流程节点或计算口径",
        "普通系统词、页面操作词、通用管理词",
        "没有通过准入的术语时",
    ]:
        if phrase not in terminology_rules:
            raise AssertionError(f"terminology scope rule missing: {phrase}")

    product_type_rules = skill + framework + template
    for phrase in [
        "涉及角色必须结合主流程与用户讨论",
        "受影响角色必须与用户讨论并确认",
        "谁在什么场景下使用什么功能",
        "关联原有功能（修改时必填）",
        "有独立业务身份和生命周期",
        "状态归类",
        "既有 / 新增 / 修改",
        "只写本次相关的新增或修改项",
        "只写本次新增、修改功能或流程变化直接产生、改变或影响的异常",
        "只写本次新增、修改功能或流程变化直接新增、改变或影响的依赖",
        "只写本次新增、修改功能或流程变化直接新增、改变或影响的留痕、统计和告警要求",
    ]:
        if phrase not in product_type_rules:
            raise AssertionError(f"project-type delivery rule missing: {phrase}")

    for phrase in [
        "页面布局",
        "按钮放在哪里",
        "数据库字段",
        "技术状态机",
        "监控实现",
    ]:
        if phrase not in framework:
            raise AssertionError(f"detail boundary missing: {phrase}")

    expected_tables = [
        "| 痛点编号 | 发生场景 | 当前做法 | 真正障碍 | 业务影响 | 期望结果 |",
        "| 能力编号 | 核心业务能力 | 对应痛点/防御要求编号 | 作用对象 | 预期业务结果 |",
        "| 使用角色 | 使用场景 | 功能 | 对应能力编号 | 业务动作 | 业务对象 | 业务结果 | 版本边界 |",
        "| 变更类型 | 使用角色 | 使用场景 | 功能 | 关联原有功能（修改时必填） | 本次变化 | 对应能力编号 | 业务结果 | 兼容要求 |",
        "| 动作点 | 对应能力编号 | 输入 | 处理规则 | 输出 | 异常处理 |",
        "| 核心业务实体 | 业务定义 | 关联实体 | 生命周期 |",
        "| 变更类型 | 核心业务实体 | 原有定义或关系 | 本次变化 | 变更后定义或关系 | 生命周期影响 |",
        "| 业务对象 | 状态 | 状态归类 | 原有定义或流转 | 本次定义或流转 | 触发事件 | 下一状态 | 异常去向 |",
        "| 变更类型 | 角色 | 数据对象 | 原可见或操作边界 | 本次可见或操作边界 | 限制或例外 |",
    ]
    for table in expected_tables:
        if table not in template:
            raise AssertionError(f"project-specific function table missing: {table}")

    defensive_tables = [
        "| 异常编号 | 异常场景 | 触发条件 | 业务处理 | 是否继续主流程 | 人工介入或责任人 | 恢复方式 |",
        "| 依赖编号 | 依赖对象 | 业务用途 | 依赖负责人 | 不可用影响 | 降级或替代原则 | 当前结论 |",
        "| 兼容编号 | 影响对象 | 当前情况 | 本次变化 | 保留或转换原则 | 默认规则 | 在途业务处理 | 验证口径 | 失败处理 |",
        "| 审计编号 | 业务事件 | 操作者或来源 | 业务对象 | 必须留存的业务事实 | 查询、统计或告警用途 | 需要获知的角色 |",
    ]
    for table in defensive_tables:
        if table not in template:
            raise AssertionError(f"defensive traceability table missing: {table}")

    traceability_rules = skill + framework + template + readme
    for phrase in [
        "总体描述",
        "1 至 3 句话",
        "P1",
        "C1",
        "P1 → C1 → 功能项",
        "每项功能必须关联至少一个能力编号",
        "多个编号",
    ]:
        if phrase not in traceability_rules:
            raise AssertionError(f"traceability rule missing: {phrase}")

    if "16 个核心考量点" not in readme:
        raise AssertionError("README does not describe the 16-point framework")
    if "$biz-analysis" not in metadata:
        raise AssertionError("openai metadata default prompt must mention $biz-analysis")

    print("OK: biz-analysis structural and behavior contract passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
