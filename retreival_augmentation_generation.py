from qdrant_client import models
from qdrant_client import QdrantClient
import re
import json
import os
from dotenv import load_dotenv
# from google import genai
import google.generativeai as genai
from fastembed import TextEmbedding, SparseTextEmbedding, LateInteractionTextEmbedding
from typing import List, Dict


COLLECTION_NAME = "jpt"
CLIENT = QdrantClient(url="http://localhost:6333")
DENSE_ENCODER = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
SPARSE_ENCODER = SparseTextEmbedding("Qdrant/bm25")
LATE_ENCODER = LateInteractionTextEmbedding("colbert-ir/colbertv2.0")

def _get_product_indices(query: str) -> List[str]:
    """
    Performs a Hybrid Search (Dense, Sparse, Late-Interaction) to get product IDs.
    """
    dense_query = next(DENSE_ENCODER.query_embed(query))
    sparse_query = next(SPARSE_ENCODER.query_embed(query))
    late_query = next(LATE_ENCODER.query_embed(query))

    prefetch = [
        models.Prefetch(
            query=dense_query,
            using="dense",
            limit=10,
        ),
        models.Prefetch(
            query=models.SparseVector(**sparse_query.as_object()),
            using="sparse",
            limit=10,
        )
    ]

    # Final query using Late Interaction model for re-ranking
    query_results = CLIENT.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=prefetch,
        query=late_query,
        using="lateInteraction",
        limit=10,
        with_payload=True,
        with_vectors=False
    ).points

    # Extract and return the product IDs
    product_ids = []
    for result in query_results:
        product_id = result.payload.get("product_id") if result.payload else None
        if product_id:
             product_ids.append(product_id)
    
    return product_ids

def retrieve_relevant_documents(query: str) -> List[List[str]]:
    """
    Retrieves all relevant text chunks for the products identified by the query.
    """
    retrieved_products = _get_product_indices(query=query)
    print(f"Retrieved Product IDs for '{query}': {retrieved_products}")
    
    all_chunks = []
    
    for product_id in retrieved_products:
        # Filter to get all chunks associated with a single product ID
        product_filter =models.Filter(
            must=[
                models.FieldCondition(
                    key="product_id",
                    match=models.MatchValue(value=product_id)
                )
            ]
        )

        info, _ = CLIENT.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=product_filter,
            limit=30,  # Limit per product
            with_payload=True,
            with_vectors=False
        )
        
        chunks_of_a_product = []
        for point in info:
            chunk = point.payload.get("chunk", "")
            # Clean up whitespace
            cleaned_chunks = re.sub(r'[ \t]+', ' ', chunk.strip())
            chunks_of_a_product.append(cleaned_chunks)
        
        all_chunks.append(chunks_of_a_product)

    print(f"Total product document sets retrieved: {len(all_chunks)}")
    return all_chunks

# --- GEMINI TOOL FUNCTIONS ---

def query_generation(base_query: str) -> Dict[str, List[str]]:
    """
    Tool 1: Generates diverse sub-queries based on a user's initial query.
    """
    generator_model = genai.GenerativeModel('gemini-2.5-flash-lite')
    
    prompt = f"""
Based on the following user query, generate a list of 5 diverse and highly specific search queries. The list MUST cover:
1.  A query focused on **Price and Value comparison** of the product, including its current market price versus its launch price, or pricing across major retailers.
2.  A query for a **Detailed component-level specification comparison** (e.g., CPU model, specific GPU VRAM, panel type, and port selection) against top competitors.
3.  A query focused on **Real-world performance benchmarks and use-case analysis** (e.g., specific FPS in popular games, video rendering times, or battery life under load).
4.  A query specifically targeting **Reviews and expert opinions** that directly compare the base_query product against its single main competitor in the same market range.
5.  The **original query itself**.

base_query = {base_query}

**Return only a single JSON array of strings, with absolutely no surrounding text, comments, or markdown formatting.**
"""

    response = generator_model.generate_content(prompt)

    print(f"\n[DEBUG: Tool 1] Raw model output: {response.text}")

    sub_queries_list= []
    try:
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("` \n").replace("json", "", 1).strip()
            
        sub_queries_list = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"\n[ERROR: Tool 1] Failed to parse JSON: {e}. Falling back to original query.")
        sub_queries_list = [base_query]  

    return {"query_list": sub_queries_list}


def deep_thinking_retrieval(query_list):
    """
    Tool 2: Gets the list of subqueries and calls the retrieval function for each one.
    Returns a JSON string of retrieved documents grouped by query.
    """
    documents_by_query = {}
    
    for query in query_list:
        document = retrieve_relevant_documents(query=query)
        documents_by_query[query] = document
        
    final_documents_json = json.dumps(documents_by_query, indent=2, ensure_ascii=False)
    print(f"\n[DEBUG: Tool 2] Documents retrieved for {len(query_list)} queries.")
    return final_documents_json

# --- MAIN CHAT FUNCTION ---

def chat(prompt: str):
    """
    The main function orchestrating the chat and tool-calling logic.
    """
    
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")    
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")
    
    genai.configure(api_key=api_key)

    chat_model = genai.GenerativeModel(
        model_name="gemini-2.5-flash-lite", 
        tools=[query_generation, deep_thinking_retrieval]
    )
    
    chat_session = chat_model.start_chat()

    initial_prompt = f"""
    Your task is to help the user (a probable customer) find a laptop according to his/her need. Follow these instructions strictly:
    1. First, call the "query_generation" tool with the user's query.
    2. After you get the list of sub_queries, you MUST call the 'deep_thinking_retrieval' tool using that list as a parameter.
    3. Finally, use the retrieved documents to answer all the queries such as price comparision, specification comparision, X VS Y Laptop Brands where X is the laptop searched by the user, Use cases(Gaming, Light Weight use-case)
    4. Include all the possible answers analysing the retrieved docs and the all the queries generated.
    5. Give a detailed answer that covers all the concerns of the user without him/her having to explain much in their query.

    User Query: "{prompt}"
    """
    
    # --- STEP 1: Call query_generation ---
    response = chat_session.send_message(initial_prompt)

    try:
        function_call = response.candidates[0].content.parts[0].function_call
        if function_call is None or function_call.name != "query_generation":
            raise ValueError("Model did not call the expected first function: query_generation")
        print(f"\n[AI] Decided to call Tool 1:{function_call.name}")
    except (IndexError, AttributeError, ValueError):
        print("\n[AI] : The model didn't call a function and responded with text instead:")
        print(response.text)
        return

    # Execute Tool 1
    args = function_call.args    
    tool_one_response_content = query_generation(base_query=args.get('base_query', prompt))
    sub_queries = tool_one_response_content.get("query_list", [])

    # Send Tool 1 result back to the model
    response = chat_session.send_message({
    "function_response": {
        "name": "query_generation",
        "response": {"query_list": sub_queries}
    }
    })

    # --- STEP 2: Call deep_thinking_retrieval ---
    try:
        function_call = response.candidates[0].content.parts[0].function_call
        if function_call is None or function_call.name != "deep_thinking_retrieval":
            raise ValueError("Model did not call the expected second function: deep_thinking_retrieval")
        print(f"\n[AI] Decided to call Tool 2:{function_call.name}")
    except (IndexError, AttributeError, ValueError):
        print("\n[AI] : The model didn't call a function and responded with text instead:")
        print(response.text)
        return

    # Execute Tool 2
    # The original logic uses the generated sub_queries list, ignoring the model's suggested args for this call
    tool_two_response_content = deep_thinking_retrieval(query_list=sub_queries)
    docs_dict = json.loads(tool_two_response_content)

    # Send Tool 2 result back to the model
    response = chat_session.send_message({"function_response":{
        "name":"deep_thinking_retrieval",
        "response": {"documents": docs_dict}
    }})
    
    # --- STEP 3: Final Answer Generation ---
    final_answer = response.candidates[0].content.parts[0].text
    print("\n--- FINAL ASSISTANT RESPONSE ---")
    print(final_answer)

# --- Execution Block ---

if __name__ == '__main__':
    user_prompt = "Acer Laptop"
    chat(user_prompt)
