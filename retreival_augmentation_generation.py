from qdrant_client import models
from qdrant_client import QdrantClient
import re
import json
import os
from dotenv import load_dotenv
import google.generativeai as genai
from fastembed import TextEmbedding, SparseTextEmbedding, LateInteractionTextEmbedding
from typing import List, Dict
import streamlit as st


COLLECTION_NAME = "Laptops_mudita"
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


    query_results = CLIENT.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=prefetch,
        query=late_query,
        using="lateInteraction",
        limit=10,
        with_payload=True,
        with_vectors=False
    ).points

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
            limit=30,
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
    
    chat_session = chat_model.start_chat(enable_automatic_function_calling=False)

    initial_prompt = f"""
    Your task is to help the user (a probable customer) find a laptop according to his/her need. Follow these instructions strictly:
    1. First, call the "query_generation" tool with the user's query.
    2. After you get the list of sub_queries, you MUST call the 'deep_thinking_retrieval' tool using that list as a parameter.
    3. Finally, use the retrieved documents to answer all the queries such as price comparision, specification comparision, X VS Y Laptop Brands where X is the laptop searched by the user, Use cases(Gaming, Light Weight use-case)
    4. Include all the possible answers analysing the retrieved docs and the all the queries generated.
    5. Give a detailed answer that covers all the concerns of the user without him/her having to explain much in their query.
    6. Provide the details of products and comparison in table and also include the url of the product from the retrieved documents.

    User Query: "{prompt}"
    """
    
    response = chat_session.send_message(initial_prompt)

    try:
        function_call = response.candidates[0].content.parts[0].function_call
        if function_call is None or function_call.name != "query_generation":
            return response.text 
            
    except (IndexError, AttributeError, ValueError) as e:
        print("\n[AI] : The model didn't call a function and responded with text instead or an error occurred.")
        return f"Tool 1 Error or unexpected model response: {response.text or str(e)}"


    args = function_call.args    
    tool_one_response_content = query_generation(base_query=args.get('base_query', prompt))
    sub_queries = tool_one_response_content.get("query_list", [])

    response = chat_session.send_message({
    "function_response": {
        "name": "query_generation",
        "response": {"query_list": sub_queries}
    }
    })
    try:
        function_call= response.candidates[0].content.parts[0].function_call
        if function_call is None or function_call.name != "deep_thinking_retrieval":
            return response.text
    except (IndexError, AttributeError, ValueError) as e:
        print("\n[AI] : The model didn't call a function and responded with text instead or an error occurred.")
        return f"Tool 2 Error or unexpected model response: {response.text or str(e)}"


  
    tool_two_response_content = deep_thinking_retrieval(query_list=sub_queries)
    docs_dict = json.loads(tool_two_response_content)

   
    response = chat_session.send_message({"function_response":{
        "name":"deep_thinking_retrieval",
        "response": {"documents": docs_dict}
    }})
    
 
    final_answer = response.text
    
  
    return final_answer


def rag_ui():
    """Sets up the Streamlit interface and orchestrates the RAG run."""
    st.set_page_config(
        page_title="Deep Thinking RAG System",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    st.title("Deep Thinking RAG System for Laptop Comparison")
    st.markdown("Enter your query to start the multi-step, tool-augmented analysis.")
    st.markdown("---")

    user_prompt = st.text_input(
        "**Enter Your Laptop Query:**",
        placeholder="e.g., Compare the latest Dell XPS 13 with the HP Spectre x360 on price and battery life.",
        key="user_query"
    )

    
    if st.button("**Start Deep Analysis**", type="primary"):
        if not user_prompt:
            st.error("Please enter a query to analyze.")
            return

        st.subheader("Comprehensive Analysis Result")
        
        with st.spinner("Running RAG pipeline: Query Generation, Retrieval, and Synthesis... (Check console for debug logs)"):
            try:
                final_answer = chat(user_prompt)
                
                st.markdown(final_answer)
                
            except ValueError as e:
                st.error(f"Configuration Error: {e}")
            except Exception as e:
                st.error(f"An unexpected error occurred during the RAG process. Please check Qdrant connection, FastEmbed models, or API settings. Error: {e}")


if __name__ == '__main__':
    rag_ui()
                                                                                                                                                                                                                                                                                                                                            