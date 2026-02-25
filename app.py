# -*- coding: utf-8 -*-

import streamlit as st
import requests

# ================= CONFIG =================
MONDAY_API_KEY = st.secrets["MONDAY_API_KEY"]
HF_API_KEY = st.secrets["HF_API_KEY"]

MONDAY_URL = "https://api.monday.com/v2"

# Hugging Face Chat Completions API (NEW)
HF_CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
HF_MODEL_NAME = "meta-llama/Llama-3.1-8B-Instruct"

BOARD_IDS = [5026839123, 5026839113]
# =========================================


# ---------- SESSION MEMORY ----------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# ---------- PROMPT BUILDER ----------
def build_prompt(question, context):
    return f"""
You are a professional business assistant analyzing task and deal data.

IMPORTANT RULES:
- Use ONLY the data provided.
- Do NOT guess or invent values.
- If information is missing, say "Not available".
- Apply logical reasoning when needed:
  - High priority > Normal
  - Unassigned tasks are risky
  - Pending tasks are urgent

DATA:
{context}

USER QUESTION:
{question}

RESPONSE FORMAT:
- Start with a short direct answer.
- Then provide details in bullet points.
- Be clear and concise.

FINAL ANSWER:
"""


# ---------- FORMAT DATA ----------
def format_selected_boards(data):
    DEFAULTS = {
        "Status": "Pending",
        "Owner": "Unassigned",
        "Due Date": "No deadline",
        "Priority": "Normal",
        "Stage": "Early stage",
        "Deal Value": "Value not finalized"
    }

    text = ""
    boards = data.get("data", {}).get("boards", [])

    for board in boards:
        text += f"\nBoard: {board['name']}\n"
        text += "-" * 40 + "\n"

        for item in board.get("items_page", {}).get("items", []):
            text += f"Task: {item['name']}\n"

            for col in item.get("column_values", []):
                title = col["column"]["title"]
                value = col["text"]

                if value and value.strip():
                    text += f"{title}: {value}\n"
                elif title in DEFAULTS:
                    text += f"{title}: {DEFAULTS[title]}\n"

            text += "\n"

    return text


# ---------- FETCH MONDAY DATA ----------
def fetch_latest_context():
    query = f"""
    {{
      boards(ids: {BOARD_IDS}) {{
        name
        items_page(limit: 50) {{
          items {{
            name
            column_values {{
              text
              column {{ title }}
            }}
          }}
        }}
      }}
    }}
    """

    headers = {
        "Authorization": MONDAY_API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(
        MONDAY_URL,
        json={{"query": query}},
        headers=headers,
        timeout=30
    )

    return format_selected_boards(response.json())


# ---------- HUGGING FACE AI ----------


def ask_huggingface(question, context):
    if not context or len(context.strip()) < 20:
        yield "No sufficient data available from the boards yet."
        return

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    # ✅ 1. Keep history short and separate Context from History
    # We pass context in the System message to save tokens in the conversation loop
    payload = {
        "model": HF_MODEL_NAME,
        "messages": [
            {"role": "system", "content": f"You are a professional assistant. Context: {context[:5000]}"},
            *st.session_state.chat_history[-4:], # Only last 2 rounds
            {"role": "user", "content": question}
        ],
        "temperature": 0.3,
        "max_tokens": 500,
        "stream": True # ✅ 2. Enable Streaming
    }

    # ✅ 3. Handle the Stream response
    response = requests.post(HF_CHAT_URL, headers=headers, json=payload, stream=True, timeout=60)
    
    full_response = ""
    for line in response.iter_lines():
        if line:
            line_text = line.decode("utf-8").replace("data: ", "")
            if line_text == "[DONE]": break
            try:
                # Extract the character/word from the JSON chunk
                content = json.loads(line_text)["choices"][0]["delta"].get("content", "")
                full_response += content
                yield content # This "yields" tokens to the UI one by one
            except:
                pass


# ================= STREAMLIT UI =================
st.set_page_config(page_title="Monday AI Chatbot", layout="centered")

st.title("🤖 monday.com AI Chatbot")
st.caption("Conversational • Context-aware • Internship-ready")

# ================= STREAMLIT UI =================
# ... (title and caption code) ...

# Display chat history so it doesn't disappear
for chat in st.session_state.chat_history:
    with st.chat_message(chat["role"]):
        st.markdown(chat["content"])

question = st.chat_input("Ask a question about work orders or deals:")

if question:
    # Show user message immediately
    with st.chat_message("user"):
        st.markdown(question)

    with st.spinner("Fetching latest data..."):
        context_data = fetch_latest_context()

    # ✅ 4. Use st.write_stream for the typing effect
    with st.chat_message("assistant"):
        # This calls our streaming function and displays it live
        full_answer = st.write_stream(ask_huggingface(question, context_data))

    # ✅ 5. Save only the clean Question and Answer to history (No Prompt Bloat)
    st.session_state.chat_history.append({"role": "user", "content": question})
    st.session_state.chat_history.append({"role": "assistant", "content": full_answer})
