# -*- coding: utf-8 -*-

import streamlit as st
import requests

# ================= CONFIG =================
MONDAY_API_KEY = st.secrets["MONDAY_API_KEY"]
HF_API_KEY = st.secrets["HF_API_KEY"]

MONDAY_URL = "https://api.monday.com"

# ✅ NEW Hugging Face Chat endpoint
HF_CHAT_URL = "https://router.huggingface.co"

# ✅ Supported model for free accounts
HF_MODEL_NAME = "meta-llama/Llama-3.1-8B-Instruct"

BOARD_IDS = [5026839123, 5026839113]

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
# =========================================


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
# ⚡ EFFICIENCY: Added cache so it doesn't reload Monday.com on every click
@st.cache_data(ttl=600) 
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
        json={"query": query},
        headers=headers,
        timeout=30
    )

    return format_selected_boards(response.json())


# ---------- HUGGING FACE AI (FIXED) ----------
def ask_huggingface(question, context):
    if not context or len(context.strip()) < 20:
        return "No sufficient data available from the boards yet."

    # Limit context size (important)
    context = context[:15000] # Slightly reduced for better speed

    prompt = f"""
You are a professional business data assistant.
... (Rest of your original prompt text) ...
DATA:
{context}

USER QUESTION:
{question}

FINAL ANSWER:
"""

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    # ⚡ EFFICIENCY: Added slice [-4:] to history so the bot doesn't get 
    # slower and more expensive as the chat gets longer.
    payload = {
    "model": HF_MODEL_NAME,
    "messages": (
        [{"role": "system", "content": "You are a helpful assistant."}]
        + st.session_state.chat_history[-4:] 
        + [{"role": "user", "content": prompt}]
    ),
    "temperature": 0.3,
    "max_tokens": 300
}

    response = requests.post(
        HF_CHAT_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]

    return f"AI error: {response.status_code}"


# ================= STREAMLIT UI =================
st.set_page_config(page_title="Monday AI Chatbot", layout="centered")

st.title(" monday.com AI Chatbot (Hugging Face)")
st.caption("Live data • Stable AI • Internship-ready")

# ⚡ EFFICIENCY: Show chat history so the user remembers what was said
for chat in st.session_state.chat_history:
    with st.chat_message(chat["role"]):
        st.write(chat["content"])

question = st.text_input("Ask a question about work orders or deals:")

if question:
    with st.spinner("Fetching latest data from monday.com..."):
        context_data = fetch_latest_context()

    with st.spinner("AI is thinking..."):
        answer = ask_huggingface(question, context_data)

    st.success("Answer")
    st.write(answer)
    
    # Save to history
    st.session_state.chat_history.append({"role": "user", "content": question})
    st.session_state.chat_history.append({"role": "assistant", "content": answer})
