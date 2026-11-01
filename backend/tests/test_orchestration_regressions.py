import asyncio
import json

import httpx

from backend.app.agent.graph import WorkflowDependencies, create_civicflow_graph, run_task
from backend.app.agent.local_state import LocalCheckpointSaver
from backend.app.agent.nodes.intent import IntentNode
from backend.app.agent.schemas.intent import Intent, IntentType
from backend.app.agent.schemas.service import ServiceRecord
from backend.app.agent.schemas.source import RetrievedChunk
from backend.app.agent.services.curated_knowledge import CuratedKnowledge
from backend.app.agent.services.official_documents import OfficialDocumentFetcher
from backend.app.agent.services.requirement_extractor import GroundedRequirements
from backend.app.agent.services.service_registry import ServiceRegistry
from backend.app.agent.services.service_resolver import ServiceResolver


def service():
    return ServiceRecord(service_id="pms", name="PMS Bihar", aliases=["PMS Bihar"],
        category="education", jurisdiction="Bihar", official_docs_url="https://pmsonline.bih.nic.in/guidelines")


class IntentStub:
    def __init__(self, **updates):
        self.intent = Intent(intent="get_information", service_name="PMS Bihar", goal="get_information", requires_browser=False, **updates)
        self.calls = []

    async def extract(self, query, context=None):
        self.calls.append((query, context))
        return self.intent


class Embeddings:
    def __init__(self):
        self.batches = []

    def embed(self, texts):
        self.batches.append(texts)
        return [[1.0, 0.5] for _ in texts]


def chunk(text="Applicants need an income certificate.", chunk_id="pms:doc"):
    return RetrievedChunk(chunk_id=chunk_id, source_id="pms", service_id="pms", source_title="PMS Bihar",
        source_url="https://pmsonline.bih.nic.in/guidelines", chunk_index=0, text=text, verification_status="verified")


def test_bare_names_and_followups_reach_contextual_model():
    model = IntentStub()
    result = asyncio.run(IntentNode(model).run("NSP", {"intent": {"last_intent": "get_information"}}))
    assert result.intent is IntentType.GET_INFORMATION
    assert model.calls[0][0] == "NSP"
    assert model.calls[0][1]["intent"]


def test_catalogue_is_searched_before_judging_and_fetching():
    order = []

    async def catalog(query):
        order.append("vector_search")
        return [chunk(chunk_id="pms:catalog")]

    async def match(**kwargs):
        order.append("match_judge")
        assert [item.service_id for item in kwargs["services"]] == ["pms"]
        return "pms"

    async def fetch(*args):
        order.append("fetch_document")
        return [chunk()]

    async def relevance(query, selected, chunks, **kwargs):
        order.append("answer" if kwargs.get("answer") else "content_judge")
        return {"relevant": True, "answer": "An income certificate is required."}

    graph = create_civicflow_graph(WorkflowDependencies(intent_extractor=IntentStub(),
        service_resolver=ServiceResolver(ServiceRegistry([service()])), catalog_retriever=catalog,
        service_matcher=match, official_document_fetcher=fetch, source_relevance_judge=relevance))
    result = asyncio.run(run_task(graph, {"user_id": "test", "user_request": "PMS Bihar requirements"}, task_id="order"))
    assert order == ["vector_search", "match_judge", "fetch_document", "content_judge", "answer"]
    assert "income certificate" in result["final_summary"]
    assert "applicant_profile" not in result
    assert "__interrupt__" not in result


def test_nic_document_links_and_redirect_validation():
    requests = []

    def handle(request):
        requests.append(str(request.url))
        if request.url.path == "/guidelines":
            return httpx.Response(200, headers={"content-type": "text/html"},
                text='<a href="/eligibility">Eligibility guidelines</a><a href="https://evil.example/">Documents</a>')
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<p>Eligibility requires Bihar residence.</p>")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await OfficialDocumentFetcher(client=client)(service(), "eligibility")

    result = asyncio.run(run())
    assert len(requests) == 2
    assert any("Bihar residence" in item.text for item in result)

    requests.clear()
    def redirect(request):
        requests.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1:8000/private"})

    async def run_redirect():
        async with httpx.AsyncClient(transport=httpx.MockTransport(redirect)) as client:
            return await OfficialDocumentFetcher(client=client)(service(), "eligibility")

    assert asyncio.run(run_redirect()) == []
    assert len(requests) == 1


def test_document_download_is_bounded():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
                httpx.Response(200, headers={"content-type": "text/html"}, content=b"x" * 100))) as client:
            return await OfficialDocumentFetcher(client=client, max_bytes=20)(service())
    assert asyncio.run(run()) == []


def test_new_service_requirements_are_extracted_with_citations():
    class Model:
        async def complete_json(self, **kwargs):
            return json.dumps({"service_id": "pms", "required_documents": [
                {"document_type": "Income certificate", "source_reference": "pms:doc"},
                {"document_type": "Invented requirement", "source_reference": "missing"}]})
    knowledge = CuratedKnowledge([], {}, embeddings=Embeddings())
    result = asyncio.run(GroundedRequirements(knowledge, Model()).extract(service_id="pms", chunks=[chunk()]))
    assert [item.document_type for item in result.required_documents] == ["Income certificate"]
    assert result.sources[0].source_id == "pms:doc"


def test_custom_catalogue_is_indexed_and_all_120_builtin_records_validate(tmp_path, monkeypatch):
    registry = ServiceRegistry.default()
    assert len([item for item in registry.all() if item.category.value == "education"]) == 14
    raw = json.loads((__import__("pathlib").Path(__file__).parents[1] / "app/agent/data/service_catalog.json").read_text(encoding="utf-8-sig"))
    assert len(raw) == 120
    assert {item["service_id"] for item in raw}.issubset({item.service_id for item in registry.all()})
    custom = tmp_path / "custom.json"
    custom.write_text(json.dumps([service().model_dump(mode="json")]), encoding="utf-8")
    monkeypatch.setenv("CIVICFLOW_SERVICE_CATALOG", str(custom))
    knowledge = CuratedKnowledge.default(embeddings=Embeddings())
    chunks = asyncio.run(knowledge.search_catalog("PMS Bihar"))
    assert "pms" in {item.service_id for item in chunks}


def test_vector_cache_reuses_document_embeddings_after_restart(tmp_path):
    path = tmp_path / "vectors.npy"
    first_model = Embeddings()
    first = CuratedKnowledge([chunk()], {}, first_model, cache_path=path)
    asyncio.run(first.retrieve(service(), "income"))
    assert path.exists()
    second_model = Embeddings()
    second = CuratedKnowledge([chunk()], {}, second_model, cache_path=path)
    asyncio.run(second.retrieve(service(), "income"))
    assert second_model.batches == [["income"]]


def test_sqlite_checkpoint_resumes_after_graph_recreation(tmp_path):
    from backend.app.agent.graph import resume_task
    stub = IntentStub()
    stub.intent = stub.intent.model_copy(update={"intent": IntentType.APPLY_FOR_SERVICE, "missing_information": ["age"]})
    deps = WorkflowDependencies(intent_extractor=stub, service_resolver=ServiceResolver(ServiceRegistry([service()])))
    saver = LocalCheckpointSaver(tmp_path / "checkpoint.db")
    graph = create_civicflow_graph(deps, checkpointer=saver)
    result = asyncio.run(run_task(graph, {"user_id": "test", "user_request": "Apply for PMS Bihar"}, task_id="persisted"))
    assert result["__interrupt__"]
    saver.close()
    restored = LocalCheckpointSaver(tmp_path / "checkpoint.db")
    graph = create_civicflow_graph(deps, checkpointer=restored)
    result = asyncio.run(resume_task(graph, task_id="persisted", resume_value={"age": 21}))
    assert result["applicant_profile"]["age"] == 21
    assert not result.get("__interrupt__")
    restored.close()
