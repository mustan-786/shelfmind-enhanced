import json
import os
from datetime import date
from google import genai
from google.genai import types
import streamlit as st


def get_gemini_client():
    api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY"))
    if not api_key:
        raise ValueError(
            "Missing GEMINI_API_KEY in Streamlit Secrets or environment variables."
        )
    return genai.Client(api_key=api_key)


def audit_shelf_photo_with_ai(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    lang_name: str = "English",
):
    """Analyzes a Kirana shelf photograph to recognize products, estimate pack

    counts, and evaluate physical movement.
    """
    client = get_gemini_client()

    prompt = f"""
    You are an automated Kirana Store Shelf Inspector in India.
    Inspect this photograph of grocery shelves/racks.
    Language for observations: {lang_name}

    Tasks:
    1. Identify distinct FMCG/grocery packaged items visible on the shelves (e.g., biscuits, tea, soaps, detergents, cooking oil, spices, noodles).
    2. Estimate the visible front-facing packet or bottle count.
    3. Note shelf placement observation (e.g., 'Primary eye-level display', 'Stagnant rear shelf', 'Single leftover unit').

    Return STRICTLY a JSON array of objects:
    [
      {{
        "item_name": "Recognized Product Name",
        "estimated_count": 5,
        "shelf_observation": "Brief observation in {lang_name}"
      }}
    ]
    """

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        return json.loads(response.text), None
    except Exception as e:
        return [], str(e)


def analyze_inventory_demand(
    inventory_items: list,
    location: str = "Maharashtra, India",
    lang_name: str = "English",
):
    """Evaluates regional demand signals, seasonal spikes, and stock health."""
    if not inventory_items:
        return [], None

    current_date = date.today().strftime("%B %d, %Y")

    prompt = f"""
    You are an expert FMCG & Kirana Store supply chain analyst in {location}.
    Current Date: {current_date}
    Target Language for descriptions: {lang_name}
    
    Analyze the following shopkeeper inventory:
    {json.dumps(inventory_items, indent=2)}
    
    Evaluate each item based on:
    1. Seasonal Demand: Current month/season in {location} (monsoon, summer, winter, harvest).
    2. Upcoming Festivals & Events in the next 30-45 days (e.g., Ganesh Chaturthi, Navratri, Diwali, Makar Sankranti, Eid, local jathras).
    3. Stock Status:
       - 'SURGE': High upcoming demand.
       - 'STABLE': Regular demand.
       - 'DEAD_STOCK': Low turnover risk.

    Write the 'reason' and 'action' fields strictly in {lang_name}.
    Keep 'status' as one of the exact English enum values: "SURGE", "STABLE", "DEAD_STOCK".

    Respond STRICTLY with a valid JSON array of objects:
    [
      {{
        "item_name": "string",
        "status": "SURGE" | "STABLE" | "DEAD_STOCK",
        "reason": "Short 1-line reason in {lang_name}",
        "action": "Actionable 1-line restocking or discount advice in {lang_name}"
      }}
    ]
    """

    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        return json.loads(response.text), None
    except Exception as e:
        return [], str(e)


def generate_dead_stock_strategy(dead_items: list, lang_name: str = "English"):
    """Generates Kirana combo clearance ideas and customer counter pitches."""
    if not dead_items:
        return []

    prompt = f"""
    You are a Kirana store retail consultant in Maharashtra, India.
    Language: {lang_name}

    These grocery products have had no sales movement and are blocking shop capital:
    {json.dumps(dead_items, indent=2)}

    For each product, generate a retail clearance tactic tailored to an Indian Kirana store:
    - Counter bundle offer (e.g., Pair with tea powder or atta)
    - Direct counter discount
    - Verbal sales pitch for the shopkeeper to use with walk-in customers

    Return STRICTLY a JSON array of objects:
    [
      {{
        "item_name": "string",
        "tactic": "Short strategy tag in {lang_name}",
        "pitch": "Counter sales pitch in {lang_name}",
        "discount_recommendation": "e.g., ₹5 Off or Combo Scheme in {lang_name}"
      }}
    ]
    """

    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        return json.loads(response.text)
    except Exception:
        return []
