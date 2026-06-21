from typing import Literal

from core.model import ConfigFinding, ConfigTemplate, CompareResult, NormalizedConfig, PolicyRule


PERMIT_ACTIONS = {"permit", "pass", "allow"}


def compare_config_to_template(config: NormalizedConfig, template: ConfigTemplate) -> CompareResult:
    findings: list[ConfigFinding] = []
    matched: list[str] = []

    for module in template.required_modules:
        value = getattr(config, module, None)
        if value:
            matched.append(module)
            continue

        findings.append(
            _finding(
                findings,
                severity="high",
                module=module,
                finding_type="missing",
                expected=f"模块 {module} 存在有效配置",
                actual=f"模块 {module} 缺失或为空",
                evidence=module,
                recommendation=f"补充 {module} 模块配置后再与模板对齐",
            )
        )

    policy_patterns = template.expected_patterns.get("policy_rules", {})
    if isinstance(policy_patterns, dict):
        if policy_patterns.get("require_logging") is True:
            for rule in config.policy_rules:
                if rule.logging is False:
                    findings.append(
                        _finding(
                            findings,
                            severity="medium",
                            module="policy_rules",
                            finding_type="risky",
                            expected="策略开启日志",
                            actual=f"策略 {rule.name} 未开启日志",
                            evidence=rule.raw or rule.name,
                            recommendation="开启该策略日志，确保访问行为可追溯",
                        )
                    )

        if policy_patterns.get("forbid_any_to_any_permit") is True:
            for rule in config.policy_rules:
                if _is_any_to_any_permit(rule):
                    findings.append(
                        _finding(
                            findings,
                            severity="high",
                            module="policy_rules",
                            finding_type="risky",
                            expected="禁止 any 到 any 的放行策略",
                            actual=f"策略 {rule.name} 允许 any 到 any",
                            evidence=rule.raw or rule.name,
                            recommendation=(
                                "收敛源、目的和服务范围，避免 any 到 any 放行"
                            ),
                        )
                    )

    return CompareResult(template_id=template.template_id, findings=findings, matched=matched)


def check_snippet_against_template(
    snippet: NormalizedConfig,
    template: ConfigTemplate,
    current: NormalizedConfig | None = None,
) -> CompareResult:
    result = compare_config_to_template(snippet, template)
    if current is None:
        result.findings.append(
            _finding(
                result.findings,
                severity="info",
                module="config",
                finding_type="unknown",
                expected="提供当前完整配置",
                actual="仅提供配置脚本片段",
                evidence="snippet",
                recommendation="需要当前完整配置进行强判断",
            )
        )
    return result


def _is_any_to_any_permit(rule: PolicyRule) -> bool:
    if rule.action.strip().lower() not in PERMIT_ACTIONS:
        return False

    return (
        _is_any_value(rule.source_objects)
        and _is_any_value(rule.destination_objects)
        and _is_any_value(rule.services)
    )


def _is_any_value(values: list[str]) -> bool:
    if not values:
        return True
    return any(value.strip().lower() == "any" for value in values)


def _finding(
    findings: list[ConfigFinding],
    *,
    severity: Literal["high", "medium", "low", "info"],
    module: str,
    finding_type: Literal["missing", "mismatch", "risky", "unknown"],
    expected: str,
    actual: str,
    evidence: str,
    recommendation: str,
) -> ConfigFinding:
    return ConfigFinding(
        finding_id=f"F-{len(findings) + 1:04d}",
        severity=severity,
        module=module,
        finding_type=finding_type,
        expected=expected,
        actual=actual,
        evidence=evidence,
        recommendation=recommendation,
    )
