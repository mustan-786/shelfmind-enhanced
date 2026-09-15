import io
import json
import os
import time
from google import genai
from google.genai import types
from PIL import Image
import streamlit as st


def get_gemini_client():
  api_key = ""
  if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
  else:
    api_key = os.environ.get("GEMINI_API_KEY", "")

  if not api_key:
    st.error("⚠️ GEMINI_API_KEY not found in Streamlit Secrets.")
    return None
  return genai.Client(api_key=api_key)


def optimize_image(image_bytes):
  """Compresses large photos to speed up inference and avoid network timeouts."""
  img = Image.open(io.BytesIO(image_bytes))
  if img.mode in ("RGBA", "P"):
    img = img.convert("RGB")

  img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)

  buf = io.BytesIO()
  img.save(buf, format="JPEG", quality=82)
  return buf.getvalue()


def extract_invoice_data_with_ai(image_bytes, mime_type="image/jpeg"):
  client = get_gemini_client()
  if client is None:
    return []

  try:
    ready_bytes = optimize_image(image_bytes)
  except Exception:
    ready_bytes = image_bytes

  prompt = """
    You are an expert document parser for Indian Kirana grocery store wholesale bills.
    Analyze this invoice image and extract all purchased line items accurately.
    
    Extract:
    1. Item Name (standardized product SKU name).
    2. Quantity (integer).
    3. Rate (₹) (float unit wholesale rate in INR).
    4. Total (₹) (float total line amount).
    
    Return ONLY a valid JSON array of objects:
    [
      {
        "Item Name": "Product Name",
        "Quantity": 10,
        "Rate (₹)": 45.0,
        "Total (₹)": 450.0
      }
    ]
    Do not include markdown code block formatting or notes. Return raw JSON only.
    """

  # Cascade through official active models to guarantee uptime
  candidate_models = [
        'gemini-3.6-flash',
        'gemini-3.5-flash-lite',
        'gemini-3.1-pro',
  ]

  last_error = ""
  for model_name in candidate_models:
    for attempt in range(3):
      try:
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_bytes(
                    data=ready_bytes,
                    mime_type="image/jpeg",
                ),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        raw_output = response.text.strip()

        if "```json" in raw_output:
          raw_output = raw_output.split("```json")[1].split("```")[0]
        elif "```" in raw_output:
          raw_output = raw_output.split("```")[1].split("```")[0]

        data = json.loads(raw_output.strip())
        return data

      except Exception as e:
        err_str = str(e)
        last_error = err_str
        # If 503 capacity surge occurs, wait with exponential backoff and retry
        if "503" in err_str or "UNAVAILABLE" in err_str:
          time.sleep(1.5 * (attempt + 1))
          continue
        # If model is deprecated or not found (404), move to next candidate immediately
        elif "404" in err_str or "NOT_FOUND" in err_str:
          break
        else:
          break

  st.error(f"Vision AI Engine Error: {last_error}")
  return []
