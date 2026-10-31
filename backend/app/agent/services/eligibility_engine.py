from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from numbers import Real
from typing import Any

from backend.app.agent.schemas.eligibility import (
    EligibilityResult,
    EligibilityStatus,
    RuleResult,
)
from backend.app.agent.schemas.requirements import (
    EligibilityOperator,
    EligibilityRule,
    ServiceRequirements,
)


_MISSING = object()


class _RuleInputError(ValueError):
    pass


def _lookup_field(profile: Mapping[str, Any], path: str) -> Any:
    value: Any = profile
    for key in path.split("."):
        if not isinstance(value, Mapping) or key not in value:
            return _MISSING
        value = value[key]
    return value


def _is_number(value: Any) -> bool:
    return isinstance(value, (Real, Decimal)) and not isinstance(value, bool)


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise _RuleInputError("expected an ISO date string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise _RuleInputError("expected an ISO date string") from exc


def _same_value_type(left: Any, right: Any) -> bool:
    if _is_number(left) and _is_number(right):
        return True
    return type(left) is type(right)


def _evaluate(operator: EligibilityOperator, actual: Any, expected: Any) -> bool:
    if operator is EligibilityOperator.IS_PRESENT:
        return actual is not _MISSING and actual is not None and actual != ""
    if operator in {EligibilityOperator.EQUALS, EligibilityOperator.NOT_EQUALS}:
        if not _same_value_type(actual, expected):
            raise _RuleInputError("profile value and rule value have incompatible types")
        return (actual == expected) if operator is EligibilityOperator.EQUALS else (actual != expected)
    if operator in {
        EligibilityOperator.GREATER_THAN,
        EligibilityOperator.LESS_THAN,
        EligibilityOperator.GREATER_THAN_OR_EQUAL,
        EligibilityOperator.LESS_THAN_OR_EQUAL,
    }:
        if not _is_number(actual) or not _is_number(expected):
            raise _RuleInputError("numeric comparison requires numeric profile and rule values")
        if operator is EligibilityOperator.GREATER_THAN:
            return actual > expected
        if operator is EligibilityOperator.LESS_THAN:
            return actual < expected
        if operator is EligibilityOperator.GREATER_THAN_OR_EQUAL:
            return actual >= expected
        return actual <= expected
    if operator in {EligibilityOperator.IN, EligibilityOperator.NOT_IN}:
        if not isinstance(expected, list):
            raise _RuleInputError("in/not_in rule value must be a list")
        if any(not _same_value_type(actual, item) for item in expected):
            raise _RuleInputError("profile value and allowed values have incompatible types")
        included = actual in expected
        return included if operator is EligibilityOperator.IN else not included
    if operator is EligibilityOperator.CONTAINS:
        if not isinstance(actual, (str, list, tuple, set, dict)):
            raise _RuleInputError("contains requires a string, list, tuple, set, or mapping profile value")
        try:
            return expected in actual
        except TypeError as exc:
            raise _RuleInputError("contains rule value is incompatible with the profile value") from exc
    if operator in {EligibilityOperator.DATE_BEFORE, EligibilityOperator.DATE_AFTER}:
        actual_date = _as_date(actual)
        expected_date = _as_date(expected)
        return (
            actual_date < expected_date
            if operator is EligibilityOperator.DATE_BEFORE
            else actual_date > expected_date
        )
    raise _RuleInputError("unsupported rule operator")


class EligibilityEngine:
    """Evaluate service rules deterministically without making legal guarantees."""

    def evaluate(
        self,
        rules: list[EligibilityRule],
        profile: Mapping[str, Any],
    ) -> EligibilityResult:
        if not rules:
            return EligibilityResult(
                status=EligibilityStatus.INSUFFICIENT_INFORMATION,
                missing_fields=["eligibility_rules"],
                validation_errors=["No sourced eligibility rules are available."],
            )

        passed: list[RuleResult] = []
        failed: list[RuleResult] = []
        missing_fields: list[str] = []
        validation_errors: list[str] = []
        sources: list[str] = []
        unknown_count = 0

        for index, rule in enumerate(rules, start=1):
            rule_id = f"rule_{index:03d}"
            if rule.source_reference and rule.source_reference not in sources:
                sources.append(rule.source_reference)
            actual = _lookup_field(profile, rule.field)
            if actual is _MISSING:
                if rule.field not in missing_fields:
                    missing_fields.append(rule.field)
                unknown_count += 1
                continue
            if rule.operator is EligibilityOperator.IS_PRESENT and actual in (None, ""):
                if rule.field not in missing_fields:
                    missing_fields.append(rule.field)
                unknown_count += 1
                continue
            try:
                matched = _evaluate(rule.operator, actual, rule.value)
            except (_RuleInputError, InvalidOperation) as exc:
                validation_errors.append(f"{rule_id} ({rule.field}): {exc}")
                unknown_count += 1
                continue
            result = RuleResult(
                rule_id=rule_id,
                passed=matched,
                explanation=(
                    f"Field '{rule.field}' satisfies the sourced rule."
                    if matched
                    else f"Field '{rule.field}' does not satisfy the sourced rule."
                ),
                source_reference=rule.source_reference,
            )
            (passed if matched else failed).append(result)

        if missing_fields or unknown_count:
            status = EligibilityStatus.INSUFFICIENT_INFORMATION
        elif failed:
            status = EligibilityStatus.NOT_ELIGIBLE
        else:
            status = EligibilityStatus.POTENTIALLY_ELIGIBLE

        return EligibilityResult(
            status=status,
            passed_rules=passed,
            failed_rules=failed,
            missing_fields=missing_fields,
            supporting_sources=sources,
            validation_errors=validation_errors,
        )

    def evaluate_requirements(
        self,
        requirements: ServiceRequirements,
        profile: Mapping[str, Any],
    ) -> EligibilityResult:
        return self.evaluate(requirements.eligibility_rules, profile)
