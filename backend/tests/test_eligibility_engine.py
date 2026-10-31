from datetime import date

import pytest

from backend.app.agent.schemas.eligibility import EligibilityStatus
from backend.app.agent.schemas.requirements import EligibilityOperator, EligibilityRule, ServiceRequirements
from backend.app.agent.services.eligibility_engine import EligibilityEngine


@pytest.mark.parametrize(
    ("operator", "actual", "expected", "expected_result"),
    [
        (EligibilityOperator.EQUALS, "x", "x", True),
        (EligibilityOperator.NOT_EQUALS, "x", "y", True),
        (EligibilityOperator.GREATER_THAN, 5, 4, True),
        (EligibilityOperator.LESS_THAN, 4, 5, True),
        (EligibilityOperator.GREATER_THAN_OR_EQUAL, 5, 5, True),
        (EligibilityOperator.LESS_THAN_OR_EQUAL, 5, 5, True),
        (EligibilityOperator.IN, "x", ["x", "y"], True),
        (EligibilityOperator.NOT_IN, "z", ["x", "y"], True),
        (EligibilityOperator.CONTAINS, ["x", "y"], "x", True),
        (EligibilityOperator.IS_PRESENT, "available", None, True),
        (EligibilityOperator.DATE_BEFORE, "2020-01-01", "2021-01-01", True),
        (EligibilityOperator.DATE_AFTER, date(2022, 1, 1), "2021-01-01", True),
    ],
)
def test_supported_rule_operators_are_deterministic(
    operator: EligibilityOperator,
    actual: object,
    expected: object,
    expected_result: bool,
) -> None:
    result = EligibilityEngine().evaluate(
        [
            EligibilityRule(
                field="value",
                operator=operator,
                value=expected,
                source_reference="source-page-1",
            )
        ],
        {"value": actual},
    )
    assert result.status is EligibilityStatus.POTENTIALLY_ELIGIBLE
    assert result.passed_rules[0].passed is expected_result
    assert result.supporting_sources == ["source-page-1"]


def test_failed_rule_returns_not_eligible_with_traceable_failure() -> None:
    result = EligibilityEngine().evaluate(
        [
            EligibilityRule(
                field="annual_income",
                operator=EligibilityOperator.LESS_THAN_OR_EQUAL,
                value=100,
                source_reference="source-income",
            )
        ],
        {"annual_income": 150},
    )
    assert result.status is EligibilityStatus.NOT_ELIGIBLE
    assert len(result.failed_rules) == 1
    assert result.failed_rules[0].source_reference == "source-income"


def test_missing_or_mistyped_data_is_insufficient_not_ineligible() -> None:
    engine = EligibilityEngine()
    rule = EligibilityRule(field="profile.age", operator=EligibilityOperator.GREATER_THAN, value=18)

    missing = engine.evaluate([rule], {"profile": {}})
    assert missing.status is EligibilityStatus.INSUFFICIENT_INFORMATION
    assert missing.missing_fields == ["profile.age"]
    assert not missing.failed_rules

    mistyped = engine.evaluate([rule], {"profile": {"age": "adult"}})
    assert mistyped.status is EligibilityStatus.INSUFFICIENT_INFORMATION
    assert not mistyped.failed_rules
    assert mistyped.validation_errors


def test_explicitly_absent_required_data_is_insufficient_information() -> None:
    rule = EligibilityRule(field="identity_number", operator=EligibilityOperator.IS_PRESENT)
    result = EligibilityEngine().evaluate([rule], {"identity_number": None})
    assert result.status is EligibilityStatus.INSUFFICIENT_INFORMATION
    assert result.missing_fields == ["identity_number"]


def test_empty_rules_and_uncited_requirements_do_not_imply_eligibility() -> None:
    result = EligibilityEngine().evaluate_requirements(
        ServiceRequirements(service_id="sample-service"),
        {"age": 25},
    )
    assert result.status is EligibilityStatus.INSUFFICIENT_INFORMATION
    assert result.missing_fields == ["eligibility_rules"]
