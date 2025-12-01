import os
import streamlit as st
import sys
import asyncio

from pathlib import Path
from dotenv import load_dotenv
from google.adk.apps import App
from google import genai
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai import types
from google.adk.sessions import InMemorySessionService
from nsk_bearing_lock_nuts.retreival import retrieval_nsk
from Misumi_bearing_lock_nuts.retreival import retrieval_misumi

from qdrant_client import QdrantClient
client=QdrantClient(url="http://localhost:6333")
load_dotenv()
api_key=os.getenv("GOOGLE_API_KEY")


def query_database_tool(query):
    """
    Queries both Misumi and NSK databases for relevant documents.
    """
    try:
        
        docs_nsk = retrieval_nsk(query)
        docs_misumi = retrieval_misumi(query)
        retrieved_docs = (docs_nsk or []) + (docs_misumi or [])

        if retrieved_docs:
            print("\nRAW RETRIEVED CONTEXT")
            for doc in retrieved_docs:
                print(doc)
                print(f"RAG tool found {len(retrieved_docs)} relevant documents")
        else:
            print("RAG tool found no relevant documents.")
    except Exception as e:
        print(f"RAG query failed: {e}")
    return retrieved_docs

def counting_parts_no():
    """
    Accurately counts the number of unique sub-categories by using the 'product_id' field.
    Returns a direct numerical summary.
    """
    res_misumi,_=client.scroll(
        collection_name="Misumi Bearing Lock Nuts",
        limit=1,
        with_payload=True,
        with_vectors=False,
        order_by = {
            "key" : "chunk_id",
            "direction" : "desc"
        }

    )
    
    product_no_misumi=res_misumi[0].payload.get("product_id")
    total_misumi=product_no_misumi+1

    res_nsk,_=client.scroll(
        collection_name="NSK Bearing Lock Nuts",
        limit=1,
        with_payload=True,
        with_vectors=False,
        order_by = {
            "key" : "chunk_id",
            "direction" : "desc"
        }

    )
    product_no_nsk=res_nsk[0].payload.get("product_id")
    total_nsk=product_no_nsk+1

    facet_response_misumi = client.facet(
    collection_name="Misumi Bearing Lock Nuts",
    key="sub_category_name",
    exact = True,
    limit=100
    )

    result_misumi = {hit.value: hit.count for hit in facet_response_misumi.hits}

    facet_response_nsk = client.facet(
    collection_name="NSK Bearing Lock Nuts",
    key="sub_category_name",
    exact = True,
    limit=150
    )
    result_nsk = {hit.value: hit.count for hit in facet_response_nsk.hits}
    return {
        "total_misumi": total_misumi,
        "total_nsk": total_nsk,
        "misumi_subcategories": result_misumi,
        "nsk_subcategories": result_nsk
    }
DefaultAgent = LlmAgent(
    name = "default_agent",
    model= "gemini-2.5-flash-lite",
    description="Give a default answer when the queries are unrelated to mechanical parts or greetings.",
    instruction="""
    You are a part of a system which answers about mechanical parts known as the `Part Numbers`. You are responsible for generating the default answers when the queries are unrelated to mechanical parts or greetings.

    #Examples
    User: Who is the president of Nepal.
    Agent: I can answer questions only related to mechanical parts.

    **Don't just use the example to generate the answer. Create different sentences that refers to saying "I cannot perform the given task".**
    """,
    output_key="default_answers"

)
    
self_description_agent=LlmAgent(
    name="SelfDescriptionAgent",
    model="gemini-2.5-flash-lite",
    description="Describes the capabilities of the system. ",
    instruction="""
    You are a part of the system which contain an agent called "Mechanical part agent" which answers the questions based on the mechanical parts,
    so your job is to answer about the capabilities of the system what it can do and how it works.

    #Examples
    User:What can you do?
    Agent: I can answer question related to the mechanical parts present in the Misumi and Nsk website.

    Here are the list of capabilities:
    1. I can use built-in database to search for the specific mechanical parts like Bearing lock nuts.
    2. I can retrieve technical specification such as material, hardness, thread size and part numbers from Misumi and NSK data.
    3. I can compare different parts based on their specification to help you find right fit.
    4. I can maintain context so that you can sak follow-up questions about the parts we are discussing.
    """,
    output_key="self_description_answer"

)

mechanical_part_agent=LlmAgent(
    name="MechanicalPartAgent",
    model="gemini-2.5-flash-lite",
    description="Search internal database for mechanical parts (Bearing Lock nuts) using RAG",
    instruction="""
    You are a part of a system which generates or answers of the users asking about the mechanical parts. You are resposible for answering the queries of the users.
    # Your tasks:

    ## Analyse the user's query. Understand the user's intent on what the user is intending to know about.

    ### Queries about the part numbers (e.g. "List out different `bearing lock nuts`", "Tell me about `C-AN00`")
    1. First you MUST call the tool "retrieval" to retrieve the  releveant documents from the user query.
    2. Analyse the list of retrieved docs and generate the proper table format.
    3. Analyse the retrieved documents and see if the schema is different. The retrieved documents are a single row in "Part Number Name: value 1 | Price: value 2 | ... |".
    4. The retrieved documents can have different schema. So, if it is different you MUST divide the table and mention the **sub-category** field on top of each table generated.
    5. If the user's query is specific about a Part Number (e.g. `C-AN00`) then list out only that product in a table. Leave out all other retrieved products.
    6. If the user's query is not a specific part number (e.g. "List out different `bearing lock nuts`" or "bearing lock nuts an type"), then list out all the retrieved products in tables.
    7. **Do not miss any "attribute_name | value" pair from the retrieved documents in the table.**
    8. URL are must for each product in the table.

    ### Queries about the number of part numbers available (e.g. "How many part-numbers are available", "How many subcategories are there in Bearing lock nuts.")
    1. First you MUST call the tool "scrolling_function" to get the number of products availbale.
    The tool returns:
    - total_misumi
    - total_nsk
    - misumi_subcategories (dict)
    - nsk_subcategories (dict)

    **You MUST:**
    #### If the user is not asking for a specific website (e.g. `Misumi` or `NSK`) then just display every returned values in proper format.
    - Display for both the websites.

    #### If the user is asking about the specific website i.e. either "Misumi" or "NSK".
    - Then just use the returned values for that specific website (e.g. If the user specifies "Misumi" then display the `total_misumi` and `misumi_subcategories`)
    - Display them in proper format using tables and raw text.

    2. Display the totals clearly
    - Convert each dictionary into a clean table with two columns: `(Sub-category, Part Numbers)`
    **| Sub-category | Count |**
    - At the bottom of each table, write: "Total sub-categories = value from the function (e.g. total_misumi or total_nsk)".
    
    3. Just generate a raw text mentioning the number of sub categories. **ONLY USE THE VALUES RETURNED FROM THE FUNCTION CALL.**
    4. Always display the total and the subcategories table. Don't just display one of them.
    """,
    tools=[counting_parts_no,query_database_tool],
    output_key="rag_agents_answers"
)

router_agent=LlmAgent(
    name="MechanicalRouter",
    model="gemini-2.5-flash-lite",
    description="The main router for the Mechnical Part Query System",
    instruction="""
    You are the Router for the Mechanical Part System. Your job is to analyze the user's query and delegate the task to appropiate sub-agent.

    1. ** Capabilities & Greetings:**
    -If user's query is a greeting(E.g: "Hi", "Hello") or asks about wht you can do(eg: "What can you do?"), "how does this work?", delegate to the SelfDescriptionAgent".

    2. **Technical & Product Queries:**
    - If the user's query is about the mechanical parts, specifically Bearing Lock Nuts, part numbers, technical specification(like thread size, material), or 
    comparisons between parts, delegate to the 'MechanicalPartAgent'.
    
    3. ** Default **
    - - If the user's query is about something other than the two mentioned above, delegate to the DefaultAgent.
    4. **Statistics & Counting:**
    - If the user's query is about the "how many products are there in misumi or nsk?","count the part numbers","give a summary of categories", then delegate to 'counting_parts_no'.

    ** Strict Rule:** Donot try to answer the user's question directly.Your only task is to choose sub-agentfrom lists.self_description_agent

    """,
    sub_agents=[self_description_agent,mechanical_part_agent,DefaultAgent]
)


App_name="mechanical_parts_rag"
User_id="user_engineer"
Session_id="session_001"
session_service=InMemorySessionService()
session=session_service.create_session_sync(
    app_name=App_name,
    user_id=User_id,
    session_id=Session_id
)
app=App(
    name=App_name,
    root_agent=router_agent
)
runner=Runner(
    app=app,
    session_service=session_service
)

async def chat_with_agent(query):
    """
    Sends the user query to the Runner and waits for the Final response.

    """
    content=types.Content(role='user',parts=[types.Part(text=query)])
    events=runner.run(user_id=User_id,session_id=Session_id,new_message=content)
    for event in events:
        if event.is_final_response():
            try:
                final_response=event.content.parts[0].text
                return final_response
            except(IndexError,AttributeError):
                return "Agent returned an empty response."
    return "No final response received from the agent."

