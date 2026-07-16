"""Track A — RAG retrieval tool (Vertex AI Search).

The agent uses this to semantically search the handbook corpus you ingested into
a Vertex AI Search data store (see rag/). It returns grounded context + citations.

Prerequisite: complete rag/README.md (terraform apply, ingest, verify) first.
"""
from .. import config


def search_policy_docs(query: str) -> dict:
    """Semantic search over the HR policy corpus in Vertex AI Search.

    Args:
        query: a natural-language policy question or search phrase.

    Returns:
        {"grounded_context": str, "citations": [str, ...]}
    """
    # TODO(you): query Vertex AI Search with the Discovery Engine client and return
    #   the extracted context + citation links.
    #
    # HINT:
    #   from google.cloud import discoveryengine_v1 as discoveryengine
    #   client = discoveryengine.SearchServiceClient(...)
    #   serving_config = f"projects/{config.GOOGLE_CLOUD_PROJECT}/locations/" \
    #       f"{config.VERTEX_AI_SEARCH_LOCATION}/collections/default_collection/" \
    #       f"engines/{config.VERTEX_AI_SEARCH_ENGINE_ID}/servingConfigs/default_search"
    #   Use a ContentSearchSpec with extractive segments/answers, then read
    #   result.document.derived_struct_data for "extractive_segments" / "link".
    #   rag/verify-rag-search.py has a working query + parser you can mirror.
    #
    # Suggested coding-agent prompt:
    #   "Implement search_policy_docs(query) using google-cloud-discoveryengine:
    #    query the engine from config, extract segments and links, and return
    #    {'grounded_context': str, 'citations': [str]}. Mirror rag/verify-rag-search.py."
    raise NotImplementedError("Implement search_policy_docs()")
