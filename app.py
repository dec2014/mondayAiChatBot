# -*- coding: utf-8 -*-

import streamlit as st
import requests
import google.generativeai as genai

# ================= CONFIG =================
MONDAY_API_KEY = st.secrets["MONDAY_API_KEY"]

GEMINI_KEYS = [
    st.secrets["GEMINI_API_KEY_1"],
    st.secrets["GEMINI_API_KEY_2"],
    st.secrets["GEMINI_API_KEY_3"],
]

MONDAY_URL = "https://api.monday.com/v2"
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


# ---------- GEMINI WITH API ROTATION ----------
def ask_gemini_with_rotation(question, context):
    if not context or len(context.strip()) < 20:
        return "No sufficient data available from the boards yet."

    prompt = f"""
You are an assistant that answers questions using ONLY the data below.
Do not guess or add new information.

DATA:
{context}

QUESTION:
{question}

ANSWER:
"""

    for idx, api_key in enumerate(GEMINI_KEYS, start=1):
        try:
            genai.configure(api_key=api_key)

            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.2,
                    "max_output_tokens": 400
                }
            )

            return response.text

        except Exception as e:
            # Try next key automatically
            print(f"Gemini key {idx} failed: {e}")
            continue

    return "All AI keys are currently exhausted. Please try again later."


# ================= STREAMLIT UI =================
st.set_page_config(page_title="Monday AI Chatbot (Gemini)", layout="centered")

st.title("🤖 monday.com AI Chatbot (Google Gemini)")
st.caption("Live data • Auto key rotation • Stable AI")

question = st.text_input("Ask a question about work orders or deals:")

if question:
    with st.spinner("Fetching latest data..."):
        context_data = fetch_latest_context()

    with st.spinner("Gemini is thinking..."):
        answer = ask_gemini_with_rotation(question, context_data)

    st.success("Answer")
    st.write(answer)
