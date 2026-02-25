# -*- coding: utf-8 -*-

import streamlit as st
import requests

# ================= CONFIG =================
MONDAY_API_KEY = st.secrets["MONDAY_API_KEY"]
HF_API_KEY = st.secrets["HF_API_KEY"]

MONDAY_URL = "https://api.monday.com/v2"
HF_MODEL_URL = "https://api-inference.huggingface.co/models/google/flan-t5-large"

BOARD_IDS = [5026839123, 5026839113]
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

    r = requests.post(MONDAY_URL, json={"query": query}, headers=headers, timeout=30)
    return format_selected_boards(r.json())


# ---------- HUGGING FACE AI ----------
def ask_huggingface(question, context):
    if not context or len(context.strip()) < 20:
        return "No sufficient data available from the boards yet."

    prompt = f"""
Answer the question using ONLY the data below.

DATA:
{context}

QUESTION:
{question}

ANSWER:
"""

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}"
    }

    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 200,
            "temperature": 0.2
        }
    }

    response = requests.post(
        HF_MODEL_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    if response.status_code != 200:
        return "AI service is temporarily unavailable."

    result = response.json()
    return result[0]["generated_text"]


# ================= STREAMLIT UI =================
st.set_page_config(page_title="Monday AI Chatbot", layout="centered")

st.title("🤖 monday.com AI Chatbot (Hugging Face)")
st.caption("Live data • No strict quota • Stable demo")

question = st.text_input("Ask a question about work orders or deals:")

if question:
    with st.spinner("Fetching latest data..."):
        context_data = fetch_latest_context()

    with st.spinner("Thinking..."):
        answer = ask_huggingface(question, context_data)

    st.success("Answer")
    st.write(answer)
