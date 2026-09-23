from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import Graph


def test_invalid_marketplace_request_returns_readable_guidance():
    graph = Graph(config={})
    graph.compile()
    result = graph.invoke(
        "Hello, hi",
        ctx=InvocationContext(caller_trust_level=TrustLevel.VERIFIED_EXTERNAL),
        input_context={"conversation_history": []},
    )

    assert result["status"] == "success"
    assert result["output"].startswith("Food-label compliance request could not be processed.")
    assert "Reason:" in result["output"]
    assert "How to continue:" in result["output"]
