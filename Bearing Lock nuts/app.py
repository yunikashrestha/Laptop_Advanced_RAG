import streamlit as st
from main import chat_with_agent
import asyncio


st.set_page_config(page_title="Mechanical Part Assistant", layout="wide")
st.title("🔧 Mechanical Part Query Assistant")
st.markdown("Ask about Bearing Lock Nuts from the Misumi and NSK catalogs.")
st.divider()

with st.form(key='query_form', clear_on_submit=True):
    user_query = st.text_input(
        "Enter your query:",
        placeholder="e.g., How many sub-categories are in NSK?"
    )
    submit_button = st.form_submit_button(label='Submit Query')

if submit_button and user_query:
    with st.spinner("Processing your query... The agent is thinking..."):
            response = asyncio.run(chat_with_agent(user_query))
            st.subheader("Agent Response")
            st.markdown(response)
       

