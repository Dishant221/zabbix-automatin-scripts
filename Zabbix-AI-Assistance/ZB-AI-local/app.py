import time
import streamlit as st

from agent.agent import create_agent
from utils.logger import setup_logger

# Direct tool testing imports
from tools.es_tool import search_zabbix_docs
from tools.zabbix_tool import zabbix_api

# ---------------------------------------------------
# LOGGER
# ---------------------------------------------------
logger = setup_logger()

# ---------------------------------------------------
# STREAMLIT PAGE CONFIG
# ---------------------------------------------------
st.set_page_config(
    page_title="Zabbix AI Assistant",
    layout="wide"
)

# ---------------------------------------------------
# HEADER
# ---------------------------------------------------
st.title("🧠 Zabbix AI Assistant")
st.caption("Zabbix API + Elasticsearch RAG + LangChain Agent")

# ---------------------------------------------------
# SESSION STATE
# ---------------------------------------------------
if "assistant" not in st.session_state:
    logger.info("Creating assistant instance")
    st.session_state.assistant = create_agent()

if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------------------------------------------
# SIDEBAR DEBUG PANEL
# ---------------------------------------------------
with st.sidebar:

    st.header("⚙ Debug Panel")

    st.markdown("---")

    # ---------------------------------------------
    # TEST ELASTICSEARCH
    # ---------------------------------------------
    if st.button("Test ES Tool"):

        logger.info("Testing Elasticsearch tool")

        with st.spinner("Testing Elasticsearch..."):
            try:
                result = search_zabbix_docs(
                    query="host.get how to retrieve hosts",
                    top_k=2
                )

                st.success("Elasticsearch working")

                st.text(result)

            except Exception as e:
                logger.exception("ES tool test failed")
                st.error(str(e))

    st.markdown("---")

    # ---------------------------------------------
    # TEST ZABBIX API
    # ---------------------------------------------
    if st.button("Test Zabbix Tool"):

        logger.info("Testing Zabbix API tool")

        with st.spinner("Calling Zabbix API..."):
            try:

                result = zabbix_api(
                    method="host.get",
                    params={
                        "output": ["hostid", "host"],
                        "limit": 3
                    }
                )

                st.success("Zabbix API working")

                st.json(result)

            except Exception as e:
                logger.exception("Zabbix tool test failed")
                st.error(str(e))

    st.markdown("---")

    # ---------------------------------------------
    # TEST FULL AGENT
    # ---------------------------------------------
    if st.button("Test Full Pipeline"):

        logger.info("Testing full agent pipeline")

        with st.spinner("Running full pipeline..."):

            try:
                result = st.session_state.assistant.invoke(
                    "How many hosts are there in Zabbix?"
                )

                st.success("Pipeline completed")

                st.subheader("Answer")
                st.write(result["answer"])

                st.subheader("API Plan")
                st.json(result["api_plan"])

                st.subheader("Raw Result")
                st.json(result["api_result"])

            except Exception as e:
                logger.exception("Pipeline test failed")
                st.error(str(e))

    st.markdown("---")

    # ---------------------------------------------
    # SHOW LOGS
    # ---------------------------------------------
    if st.button("Show Logs"):

        logger.info("Showing log file")

        try:
            with open("zabbix_ai.log", "r", encoding="utf-8") as f:
                logs = f.read()

            st.text_area(
                "Application Logs",
                logs,
                height=500
            )

        except Exception as e:
            st.error(str(e))

    st.markdown("---")

    # ---------------------------------------------
    # CLEAR CHAT
    # ---------------------------------------------
    if st.button("Clear Chat"):

        logger.info("Clearing chat history")

        st.session_state.messages = []

        if "assistant" in st.session_state:
            del st.session_state["assistant"]

        st.session_state.assistant = create_agent()

        st.success("Chat cleared")

        st.rerun()

# ---------------------------------------------------
# CHAT HISTORY
# ---------------------------------------------------
for msg in st.session_state.messages:

    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# ---------------------------------------------------
# USER INPUT
# ---------------------------------------------------
user_input = st.chat_input(
    "Ask about hosts, problems, triggers, items, alerts..."
)

# ---------------------------------------------------
# MAIN CHAT FLOW
# ---------------------------------------------------
if user_input:

    logger.info(f"User question received: {user_input}")

    # Save user message
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    # Show user message
    with st.chat_message("user"):
        st.write(user_input)

    # Assistant response
    with st.chat_message("assistant"):

        # Live debug container
        debug_box = st.empty()

        with st.spinner("Thinking..."):

            try:

                # -----------------------------------------
                # STEP 1
                # -----------------------------------------
                debug_box.info("Step 1/4 : Processing question")

                logger.info("Starting assistant pipeline")

                start_time = time.time()

                # -----------------------------------------
                # RUN AGENT
                # -----------------------------------------
                result = st.session_state.assistant.invoke(user_input)

                end_time = time.time()

                execution_time = round(end_time - start_time, 2)

                logger.info(
                    f"Assistant pipeline completed in {execution_time} sec"
                )

                # -----------------------------------------
                # STEP COMPLETE
                # -----------------------------------------
                debug_box.success(
                    f"Completed in {execution_time} seconds"
                )

                # -----------------------------------------
                # FINAL ANSWER
                # -----------------------------------------
                response_text = result["answer"]

                st.write(response_text)

                # -----------------------------------------
                # DEBUG EXPANDER
                # -----------------------------------------
                with st.expander("🔍 Debug Details"):

                    st.subheader("Retrieved Docs Context")

                    st.text(result["docs_context"])

                    st.subheader("Generated API Plan")

                    st.json(result["api_plan"])

                    st.subheader("Raw Zabbix API Result")

                    st.json(result["api_result"])

            except Exception as e:

                logger.exception("Error while processing user request")

                response_text = f"Error: {str(e)}"

                st.error(response_text)

    # Save assistant message
    st.session_state.messages.append({
        "role": "assistant",
        "content": response_text
    })