from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.exists():
        raise AssertionError(f"missing required file: {relative}")
    return path.read_text(encoding="utf-8")


def require(text: str, pattern: str, label: str) -> None:
    if not re.search(pattern, text, re.MULTILINE):
        raise AssertionError(f"missing {label}: {pattern}")


def forbid(text: str, pattern: str, label: str) -> None:
    if re.search(pattern, text, re.MULTILINE):
        raise AssertionError(f"obsolete or conflicting {label}: {pattern}")


def main() -> int:
    skill = read("SKILL.md")
    framework = read("references/analysis-framework.md")
    output_guide = read("references/document-template.md")
    readme = read("README.md")
    metadata = read("agents/openai.yaml")

    # Trigger and routing contract.
    require(skill, r"(?m)^description:\s*\|\n\s+深挖", "Chinese trigger-focused description")
    for phrase in [
        "真实问题",
        "必要能力",
        "本期边界",
        "帮我梳理需求",
        "输出形式按项目和材料选择",
    ]:
        if phrase not in skill:
            raise AssertionError(f"trigger/output description missing: {phrase}")
    require(skill, r"先判断是否存在正在使用的系统或流程", "existing-system-first routing")
    require(skill, r"1\. 全新产品.*\n2\. 增量迭代.*\n3\. 小工具", "project routes")
    forbid(
        skill,
        r"整体重构，或涉及多个角色和完整业务流程",
        "ambiguous full-new-product route",
    )

    # Deep-exploration contract.
    for phrase in [
        "待验证假设",
        "事实：",
        "因果：",
        "反事实：",
        "代价与风险：",
        "最小必要范围",
        "每轮只问 2 到 4 个问题",
        "停止深挖",
    ]:
        if phrase not in skill:
            raise AssertionError(f"deep-exploration rule missing: {phrase}")

    for phrase in [
        "引导用户思考",
        "当前判断 → 判断依据 → 为什么重要",
        "最近一次真实发生的场景",
        "二选一、优先级排序、具体案例、反例",
        "简短的“当前判断 / 依据 / 影响”",
        "不要输出冗长的内部思维过程",
    ]:
        if phrase not in skill:
            raise AssertionError(f"user-guidance rule missing: {phrase}")

    # Output must be content-driven and format-flexible.
    for phrase in [
        "输出契约：不固定格式，固定内容质量",
        "输出前校验",
        "最终校验闭环",
        "最终校验是正式交付的闸门",
        "校验不通过时",
        "直到校验通过",
        "不能生成正式文档",
        "明确阻塞原因",
        "事实、观点、推测和待确认",
        "反事实检验",
        "范围外内容有排除依据",
        "不以章节数量、表格数量或 16 点覆盖率作为完成条件",
    ]:
        if phrase not in skill:
            raise AssertionError(f"content-quality contract missing: {phrase}")
    for phrase in [
        "不强制出现",
        "不强制使用 16 点表格",
        "不强制使用 Mermaid",
        "不强制使用 `P1 → C1 → 功能项` 编号链",
    ]:
        if phrase not in skill:
            raise AssertionError(f"format-flexibility rule missing: {phrase}")

    # Progressive disclosure and reference roles.
    require(skill, r"analysis-framework\.md", "analysis framework routing")
    require(skill, r"document-template\.md", "output guide routing")
    require(framework, r"风险扫描池", "risk-pool framing")
    require(framework, r"不是固定目录、问卷或输出模板", "non-template framework boundary")
    require(framework, r"反事实", "counterfactual analysis")
    require(framework, r"范围论证", "scope reasoning")
    require(framework, r"用户引导式提问", "guided-questioning section")
    require(framework, r"常见语义冲突", "semantic-conflict scan")
    require(framework, r"知识导航 vs 工作台", "navigation/workbench conflict")
    require(framework, r"最终校验不通过时不能直接交付", "iterative final gate")
    require(framework, r"停止深挖”不等于“允许交付", "stop-vs-delivery distinction")
    require(output_guide, r"输出形式不固定", "format-flexible output guide")
    require(output_guide, r"最小内容契约", "minimum content contract")
    require(output_guide, r"内容校验", "output validation")
    require(output_guide, r"可选结构示例", "optional output examples")
    require(output_guide, r"面向用户的确认摘要", "user-facing confirmation summary")
    require(output_guide, r"最终校验闸门", "final validation gate")
    require(output_guide, r"直到全部必过项通过", "validation loop")

    # Ensure the old fixed-template contract did not survive the rewrite.
    forbid(output_guide, r"先删除不适用章节，再.*连续重新编号", "fixed heading renumbering")
    forbid(output_guide, r"## 1\. 名词解释", "fixed delivery heading")
    forbid(output_guide, r"16 点覆盖率作为完成条件", "coverage as completion gate")
    forbid(readme, r"固定的 16 点 ID", "fixed point IDs in README")

    # Status, confirmation, and no-invention boundaries.
    for phrase in [
        "非阻塞待确认项",
        "阻塞性冲突",
        "当前推测",
        "不编造业务规模",
        "不通过互联网搜索推断企业内部规则",
    ]:
        if phrase not in skill:
            raise AssertionError(f"uncertainty/safety rule missing: {phrase}")

    if "$biz-analysis" not in metadata:
        raise AssertionError("openai metadata default prompt must mention $biz-analysis")
    if "16 个分析维度只作为内部风险扫描池" not in readme:
        raise AssertionError("README does not describe risk-pool behavior")

    print("OK: biz-analysis behavior and content-contract validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
