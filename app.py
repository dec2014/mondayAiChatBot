# -*- coding: utf-8 -*-

import streamlit as st
import requests
import json  # ✅ Essential for parsing the AI stream

# ================= CONFIG =================
MONDAY_API_KEY = st.secrets["MONDAY_API_KEY"]
HF_API_KEY = st.secrets["HF_API_KEY"]

MONDAY_URL = "https://api.monday.com/v2"
HF_CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
HF_MODEL_NAME = "meta-llama/Llama-3.1-8B-Instruct"

BOARD_IDS = [5026839123, 5026839113]
# =========================================

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ---------- FORMAT DATA ----------
def format_selected_boards(data):
    DEFAULTS = {
        "Status": "Pending", "Owner": "Unassigned", "Due Date": "No deadline",
        "Priority": "Normal", "Stage": "Early stage", "Deal Value": "Value not finalized"
    }
    text = ""
    boards = data.get("data", {}).get("boards", [])
    for board in boards:
        text += f"\nBoard: {board['name']}\n" + "-" * 20 + "\n"
        for item in board.get("items_page", {}).get("items", []):
            text += f"Task: {item['name']}\n"
            for col in item.get("column_values", []):
                title, value = col["column"]["title"], col["text"]
                text += f"{title}: {value if value and value.strip() else DEFAULTS.get(title, 'N/A')}\n"
            text += "\n"
    return text

# ---------- FETCH MONDAY DATA ----------
# Note: We removed @st.cache_data so it fetches live data at every message
def fetch_latest_context():
    query = f"{{ boards(ids: {BOARD_IDS}) {{ name items_page(limit: 50) {{ items {{ name column_values {{ text column {{ title }} }} }} }} }} }}"
    headers = {"Authorization": MONDAY_API_KEY, "Content-Type": "application/json"}
    
    # ✅ FIXED: Use single braces {"query": query} to avoid TypeError
    response = requests.post(MONDAY_URL, json={"query": query}, headers=headers, timeout=30)
    
    if response.status_code == 200:
        return format_selected_boards(response.json())
    return "Error: Could not fetch data from Monday.com"

# ---------- HUGGING FACE AI ----------
def ask_huggingface(question, context):
    headers = {"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"}

    # ✅ Optimized Payload: Context in System, prune history to last 4 messages
    payload = {
        "model": HF_MODEL_NAME,
        "messages": [
            {"role": "system", "content": f"You are a professional assistant. Use ONLY this data: {context[:7000]}"},
            *st.session_state.chat_history[-4:], # Pruned history
            {"role": "user", "content": question}
        ],
        "temperature": 0.2,
        "max_tokens": 500,
        "stream": True 
    }

    response = requests.post(HF_CHAT_URL, headers=headers, json=payload, stream=True, timeout=60)
    
    full_response = ""
    for line in response.iter_lines():
        if line:
            line_text = line.decode("utf-8").strip()
            if line_text.startswith("data: "):
                data_content = line_text[6:]
                if data_content == "[DONE]": break
                try:
                    # ✅ FIXED: choices[0] access for the router API
                    chunk = json.loads(data_content)
                    content = chunk["choices"][0]["delta"].get("content", "")
                    full_response += content
                    yield content
                except:
                    continue

# ================= STREAMLIT UI =================
st.set_page_config(page_title="Monday AI Chatbot", layout="centered")
st.title("🤖 monday.com AI Chatbot")

# Display Persistent Chat History
for chat in st.session_state.chat_history:
    with st.chat_message(chat["role"]):
        st.markdown(chat["content"])

# User Input
if prompt := st.chat_input("Ask about your Monday.com boards..."):
    # 1. Display User Message
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Fetch Fresh Data (Every single time)
    with st.spinner("Fetching live board data..."):
        context_data = fetch_latest_context()

    # 3. Stream Assistant Response
    with st.chat_message("assistant"):
        full_answer = st.write_stream(ask_huggingface(prompt, context_data))

    # 4. Save to session state
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    st.session_state.chat_history.append({"role": "assistant", "content": full_answer})
