import json
import os
import streamlit as st
from google import genai
from google.genai import types


def get_gemini_client():
    """Retrieves API key securely from Streamlit Secrets or Environment Variables."""
    api_key = ""
    if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
    else:
        api_key = os.environ.get("GEMINI_API_KEY", "")

    if not api_key:
        st.error("⚠️ GEMINI_API_KEY not found. Please set it in Streamlit Cloud Secrets.")
        return None
    return genai.Client(api_key=api_key)


def extract_invoice_data_with_ai(image_bytes, mime_type="image/jpeg"):
    """
    Uses Multimodal Vision AI to parse complex, tilted,
    handwritten, or dot-matrix Indian Kirana invoices into clean JSON.
    """
    client = get_gemini_client()
    if client is None:
        return []

    prompt = """
    You are an expert document parser for Indian Kirana grocery store wholesale bills.
    Analyze this invoice image and extract all purchased line items accurately.

    Even if the text is faint, dot-matrix, handwritten, or on colored/pink paper:
    1. Extract the Item Name (clean standard product name with brand and size/weight if visible).
    2. Extract the Quantity (integer).
    3. Extract the Unit Wholesale Rate in INR (float).
    4. Extract the Total Amount in INR (float).

    Return ONLY a valid JSON array of objects with these exact keys:
    [
      {
        "Item Name": "Product Name",
        "Quantity": 10,
        "Rate (₹)": 45.0,
        "Total (₹)": 450.0
      }
    ]
    Do not wrap the response in markdown formatting or explanation. Return only the raw JSON.
    """

    # Model is configurable via secrets/env so it can be bumped without a code change
    # as Google ships newer Gemini versions.
    model_name = ""
    if hasattr(st, "secrets") and "GEMINI_MODEL" in st.secrets:
        model_name = st.secrets["GEMINI_MODEL"]
    model_name = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                ),
                prompt
            ]
        )

        raw_output = response.text.strip()

        # Strip potential markdown formatting
        if "```json" in raw_output:
            raw_output = raw_output.split("```json")[1].split("```")[0]
        elif "```" in raw_output:
            raw_output = raw_output.split("```")[1].split("```")[0]

        data = json.loads(raw_output.strip())
        return data

    except Exception as e:
        st.error(f"Vision AI Engine Error: {str(e)}")
        return []
