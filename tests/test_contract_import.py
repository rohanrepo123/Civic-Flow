from civicflow_contracts import BrowserSessionCreate, Viewport


def test_browser_session_contract_validates() -> None:
    request = BrowserSessionCreate(
        task_id="task-demo",
        start_url="https://example.gov.in",
        viewport=Viewport(width=1280, height=800),
    )
    assert request.task_id == "task-demo"


def test_viewport_rejects_too_small_dimensions() -> None:
    try:
        Viewport(width=100, height=800)
    except ValueError:
        return
    raise AssertionError("invalid viewport unexpectedly validated")
