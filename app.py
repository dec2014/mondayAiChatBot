# -*- coding: utf-8 -*-
import streamlit as st
import requests
import json

# ================= CONFIG =================
MONDAY_API_KEY = st.secrets["MONDAY_API_KEY"]
HF_API_KEY = st.secrets["HF_API_KEY"]
MONDAY_URL = "https://api.monday.com"
HF_CHAT_URL = "https://router.huggingface.co"
HF_MODEL_NAME = "meta-llama/Llama-3.1-8B-Instruct"
BOARD_IDS = [5026839123, 5026839113]

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ================= DATA FETCHING (OPTIMIZED) =================
@st.cache_data(ttl=600) # ⚡ EFFICIENCY: Only hits Monday API once every 10 mins
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
    headers = {"Authorization": MONDAY_API_KEY, "Content-Type": "application/json"}
    try:
        response = requests.post(MONDAY_URL, json={"query": query}, headers=headers, timeout=15)
        data = response.json()
        
        # Compact formatting to save tokens
        text = ""
        for board in data.get("data", {}).get("boards", []):
            text += f"\n[Board: {board['name']}]\n"
            for item in board.get("items_page", {}).get("items", []):
                cols = ", ".join([f"{c['column']['title']}: {c['text']}" for c in item.get("column_values", []) if c['text']])
                text += f"- {item['name']} | {cols}\n"
        return text
    except Exception as e:
        return f"Error fetching data: {e}"

# ================= AI LOGIC (STREAMING) =================
def ask_huggingface_stream(question, context):
    # ⚡ EFFICIENCY: Only keep last 3 exchanges to avoid latency/cost bloat
    short_history = st.session_state.chat_history[-6:]
    
    system_prompt = f"""Act as a Business Analyst. Use ONLY this data:
    {context[:8000]} 
    Rules: If not in data, say 'Not found'. Use bullet points."""

    messages = [{"role": "system", "content": system_prompt}] + short_history + [{"role": "user", "content": question}]
    
    payload = {
        "model": HF_MODEL_NAME,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 500,
        "stream": True # ⚡ EFFICIENCY: Faster perceived speed
    }
    
    headers = {"Authorization": f"Bearer {HF_API_KEY}", "Content-Type": "application/json"}
    
    response = requests.post(HF_CHAT_URL, headers=headers, json=payload, stream=True, timeout=60)
    
    for line in response.iter_lines():
        if line:
            chunk = line.decode("utf-8").replace("data: ", "")
            if chunk == "[DONE]": break
            try:
                content = json.loads(chunk)["choices"][0]["delta"].get("content", "")
                yield content
            except:
                pass

# ================= STREAMLIT UI =================
st.set_page_config(page_title="Monday AI", layout="wide")
st.title("🚀 Monday.com Optimized AI")

# Display history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if prompt := st.chat_input("Ask about work orders or deals..."):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        context_data = fetch_latest_context()
        # ⚡ EFFICIENCY: Stream response directly to UI
        full_response = st.write_stream(ask_huggingface_stream(prompt, context_data))
    
    st.session_state.chat_history.append({"role": "assistant", "content": full_response})
