import asyncio

from backend.app.agent.graph import WorkflowDependencies, create_civicflow_graph, run_task
from backend.app.agent.nodes.intent import RuleBasedIntentExtractor
from backend.app.agent.services.curated_knowledge import CuratedKnowledge
from backend.app.agent.services.service_registry import ServiceRegistry
from backend.app.agent.services.service_resolver import ServiceResolver


async def main() -> None:
    registry = ServiceRegistry.default()
    knowledge = CuratedKnowledge.default()
    graph = create_civicflow_graph(
        WorkflowDependencies(
            intent_extractor=RuleBasedIntentExtractor(),
            service_resolver=ServiceResolver(registry),
            source_retriever=knowledge.retrieve,
            requirement_extractor=knowledge,
        )
    )
    requests = (
        "What documents and fees are listed for a domicile certificate in Maharashtra?",
        "What scholarship schemes are available in Maharashtra?",
    )
    for index, request in enumerate(requests, start=1):
        result = await run_task(
            graph,
            {"user_id": "demo-citizen", "user_request": request},
            task_id=f"demo-{index}",
        )
        pending = (result.get("__interrupt__") or [None])[0]
        status = "waiting_for_user" if pending else result.get("task_status", "unknown")
        print(f"\n{request}\nStatus: {status}")
        print(result.get("final_summary") or pending.value)
        requirements = result.get("requirements")
        if requirements:
            print(f"Cited sources: {len(requirements.sources)}; requirements listed: {len(requirements.required_documents)}")
            for uncertainty in requirements.uncertainties:
                print(f"Review: {uncertainty}")


if __name__ == "__main__":
    asyncio.run(main())
