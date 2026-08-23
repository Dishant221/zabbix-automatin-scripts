import json

from elasticsearch import Elasticsearch
from langchain_core.tools import StructuredTool
from sentence_transformers import SentenceTransformer

from config.settings import ES_URL, ES_API_KEY, ES_INDEX
from utils.logger import setup_logger

logger = setup_logger()

# LOAD LOCAL EMBEDDING MODEL
model = SentenceTransformer("all-MiniLM-L6-v2")

logger.info("SentenceTransformer model loaded")

# ELASTICSEARCH CLIENT
es = (
    Elasticsearch(
        ES_URL,
        api_key=ES_API_KEY,
        request_timeout=30,
        max_retries=1,
        retry_on_timeout=False
    )
    if ES_API_KEY
    else Elasticsearch(
        ES_URL,
        request_timeout=30,
        max_retries=1,
        retry_on_timeout=False
    )
)

# ---------------------------------------------------
# GENERATE EMBEDDING
# ---------------------------------------------------
def generate_embedding(text: str):

    logger.info(f"Generating embedding for: {text}")

    embedding = model.encode(
        text,
        normalize_embeddings=True
    )

    embedding = embedding.tolist()

    logger.info(
        f"Generated embedding dimension: {len(embedding)}"
    )

    return embedding

# ---------------------------------------------------
# SEARCH FUNCTION
# ---------------------------------------------------
def search_zabbix_docs(
    query: str,
    top_k: int = 4
) -> str:

    logger.info(f"ES semantic query: {query}")

    try:

        # ---------------------------------------------
        # GENERATE QUERY EMBEDDING
        # ---------------------------------------------
        query_vector = generate_embedding(query)

        # ---------------------------------------------
        # VECTOR SEARCH
        # ---------------------------------------------
        resp = es.search(
            index=ES_INDEX,
            knn={
                "field": "embedding",
                "query_vector": query_vector,
                "k": top_k,
                "num_candidates": 50
            },
            size=top_k
        )

        hits = resp.get("hits", {}).get("hits", [])

        logger.info(f"ES semantic hits: {len(hits)}")

        if not hits:

            return (
                f"No relevant Zabbix documentation found "
                f"for query: {query}"
            )

        blocks = []

        for i, hit in enumerate(hits, start=1):

            src = hit.get("_source", {})

            score = hit.get("_score", 0)

            blocks.append(
                f"""    
                    DOC {i}

                    score: {score}

                    api_name:{src.get('api_name', '')}

                    title:{src.get('title', '')}

                    chunk_type:{src.get('chunk_type', '')}

                    description:{src.get('description', '')}

                    params_example:{json.dumps(src.get('params_example', ''), indent=2, ensure_ascii=False)}

                    embedding_text:{src.get('embedding_text', '')}

                    """
                    )

        final_context = "\n\n----------------------\n\n".join(blocks)

        logger.info(
            f"Final retrieved context length: {len(final_context)}"
        )

        return final_context

    except Exception as e:

        logger.exception("Semantic ES search failed")

        return f"ERROR searching Elasticsearch: {str(e)}"

# ---------------------------------------------------
# LANGCHAIN TOOL
# ---------------------------------------------------
search_zabbix_docs_tool = StructuredTool.from_function(
    func=search_zabbix_docs,
    name="search_zabbix_docs",
    description=(
        "Semantic vector search over Zabbix API documentation "
        "stored in Elasticsearch."
    )
)