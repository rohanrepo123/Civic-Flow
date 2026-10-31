from app.graph.workflow import run_workflow

def test_workflow_runs_all_generic_stages_and_extracts_intent():
    result = run_workflow("Can you explain eligibility for this service?")
    assert result["intent"] == "eligibility_question"
    assert result["stages"] == ["intent_understanding", "service_discovery", "eligibility_evaluation",
        "document_requirement_reasoning", "missing_information_detection", "form_preparation_advice",
        "validation_explanation", "structured_response"]

def test_workflow_does_not_assume_service_specific_intent():
    result = run_workflow("Help me organize my documents", {"service_id": "generic-service"})
    assert result["intent"] == "service_assistance"
    assert "Password" not in result.get("advice", "")
