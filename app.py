import base64
from datetime import date
import io
import os
import urllib.parse
from PIL import Image
import pandas as pd
import qrcode
import streamlit as st

import database as db
from demand_radar import (
    analyze_inventory_demand,
    audit_shelf_photo_with_ai,
    generate_dead_stock_strategy,
)
from ocr_pipeline import extract_invoice_data_with_ai
import sms_service
from translations import TRANSLATIONS


def get_base64_image(image_path):
    """Encodes a local image to base64 for seamless HTML embedding."""
    if os.path.exists(image_path):
        try:
            with open(image_path, "rb") as img_file:
                encoded = base64.b64encode(img_file.read()).decode()
                ext = os.path.splitext(image_path)[1].lstrip(".").lower()
                mime = "image/png" if ext == "png" else "image/jpeg"
                return f"data:{mime};base64,{encoded}"
        except Exception:
            return None
    return None


# 1. Page configuration & Global Logo
logo_path = "smlogo.png"
logo_b64 = get_base64_image(logo_path)
page_icon = Image.open(logo_path) if os.path.exists(logo_path) else "📦"

st.set_page_config(
    page_title="SHELF MIND",
    page_icon=page_icon,
    layout="centered",
    initial_sidebar_state="collapsed",
)
logo_html = (
    f'<img src="{logo_b64}" alt="Shelf Mind Logo" style="height: 64px; max-height: 68px; width: auto; object-fit: contain; border-radius: 10px; filter: drop-shadow(0 2px 6px rgba(0,0,0,0.15));" />'
    if logo_b64
    else '<span style="font-size: 42px;">📦</span>'
)

# 2. Kotak 811 theme and styles
st.markdown("""
<style>
    .stApp {
        background-color: var(--background-color) !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        padding-bottom: 95px !important;
    }

    p, span, label, div[data-testid="stMarkdownContainer"] {
        color: var(--text-color);
    }

    .kotak-header {
        background: linear-gradient(135deg, #ED1C24 0%, #991B1B 100%);
        border-radius: 16px;
        padding: 16px 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 14px rgba(237, 28, 36, 0.25);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .kotak-header * {
        color: #FFFFFF !important;
    }
    .kotak-header h1 {
        font-size: 22px;
        font-weight: 800;
        margin: 0;
    }
    .kotak-header-sub {
        font-size: 13px;
        opacity: 0.92;
        margin-top: 3px;
    }
    .kotak-badge {
        background: rgba(255, 255, 255, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.4);
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }

    .kpi-grid {
        display: flex;
        flex-direction: column;
        gap: 12px;
        margin-bottom: 20px;
    }
    .kotak-kpi-card {
        background-color: var(--secondary-background-color) !important;
        border: 1px solid rgba(128, 128, 128, 0.22) !important;
        border-left: 5px solid #0B2265 !important;
        border-radius: 12px;
        padding: 14px 18px;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .kotak-kpi-card.accent-red {
        border-left-color: #ED1C24 !important;
    }
    .kpi-card-title {
        font-size: 15px;
        font-weight: 700;
        color: var(--text-color) !important;
    }
    .kpi-card-sub {
        font-size: 12px;
        color: var(--text-color) !important;
        opacity: 0.72;
        margin-top: 2px;
    }
    .kpi-card-amount {
        font-size: 19px;
        font-weight: 800;
        color: var(--text-color) !important;
        text-align: right;
    }
    .kpi-card-amount.red {
        color: #ED1C24 !important;
    }

    .kotak-udhar-card {
        background-color: var(--secondary-background-color) !important;
        border: 1px solid rgba(128, 128, 128, 0.22) !important;
        border-left: 5px solid #ED1C24 !important;
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 12px;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
    }
    .kotak-udhar-title {
        font-size: 16px;
        font-weight: 700;
        color: var(--text-color) !important;
    }
    .kotak-udhar-sub {
        font-size: 12px;
        color: var(--text-color) !important;
        opacity: 0.75;
        margin-top: 2px;
    }
    .kotak-udhar-note {
        font-size: 13px;
        color: var(--text-color) !important;
        opacity: 0.9;
        margin-top: 6px;
    }

    /* Primary Active Buttons */
    div.stButton > button[kind="primary"] {
        background-color: #ED1C24 !important;
        color: #FFFFFF !important;
        border-radius: 12px !important;
        border: 1px solid #ED1C24 !important;
        font-weight: 700 !important;
        box-shadow: 0 3px 10px rgba(237, 28, 36, 0.3) !important;
        transition: all 0.2s ease-in-out !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #C7141B !important;
        border-color: #C7141B !important;
        transform: translateY(-1px) !important;
    }

    /* Secondary Inactive Navigation Buttons */
    div.stButton > button[kind="secondary"] {
        background-color: var(--secondary-background-color) !important;
        color: var(--text-color) !important;
        border-radius: 12px !important;
        border: 1px solid rgba(128, 128, 128, 0.25) !important;
        font-weight: 600 !important;
        opacity: 0.85 !important;
        transition: all 0.2s ease-in-out !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        border-color: #ED1C24 !important;
        color: #ED1C24 !important;
        opacity: 1 !important;
        transform: translateY(-1px) !important;
    }

    /* Uniform Height for the 2x2 Action Navigation Grid */
    div[data-testid="stHorizontalBlock"] div.stButton > button {
        min-height: 48px !important;
        font-size: 14px !important;
    }

    .badge-surge {
        background-color: #DC2626 !important;
        color: #FFFFFF !important;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-dead {
        background-color: #D97706 !important;
        color: #FFFFFF !important;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-stable {
        background-color: #059669 !important;
        color: #FFFFFF !important;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Floating Center Scanner FAB */
    .fab-dock {
        position: fixed;
        bottom: 22px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 99999;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .fab-dock div[data-testid="stButton"] > button {
        background: linear-gradient(135deg, #ED1C24 0%, #B81319 100%) !important;
        color: #FFFFFF !important;
        border-radius: 50px !important;
        padding: 12px 28px !important;
        font-size: 15px !important;
        font-weight: 800 !important;
        letter-spacing: 0.5px !important;
        border: 2px solid #FFFFFF !important;
        box-shadow: 0 6px 20px rgba(237, 28, 36, 0.4) !important;
        transition: transform 0.2s ease !important;
    }
    .fab-dock div[data-testid="stButton"] > button:hover {
        transform: scale(1.05) !important;
        background: #C7141B !important;
    }

    header[data-testid="stHeader"] {
        background-color: transparent !important;
    }
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# 3. Database initialization and session recovery
db.init_db()

# A random session token lives in the URL instead of the raw phone number,
# so a shared/guessed link can no longer open someone else's dashboard.
query_params = st.query_params
session_token = query_params.get("session", None)

if "logged_in_store" not in st.session_state or st.session_state["logged_in_store"] is None:
    if session_token:
        restored_store = db.get_store_by_session(session_token)
        if restored_store:
            st.session_state["logged_in_store"] = restored_store
            st.session_state["session_token"] = session_token
        else:
            st.query_params.clear()

lang_col1, lang_col2 = st.columns([2, 1])
with lang_col2:
    lang_choice = st.selectbox("Language / भाषा", ["English", "मराठी", "हिंदी"], label_visibility="collapsed")
lang_key = "mr" if "मराठी" in lang_choice else "hi" if "हिंदी" in lang_choice else "en"
t = TRANSLATIONS[lang_key]


# --- TOP LEVEL DIALOG DEFINITION ---
@st.dialog(t.get("shelf_dialog_title", "📸 Store Shelf Rack Audit"))
def open_shelf_audit_dialog(current_store_phone, current_lang_choice):
    st.caption(t.get("shelf_dialog_sub", "Point your camera at the store shelf to capture current inventory arrangement."))
    shelf_img = st.camera_input(t.get("shelf_dialog_snap", "Snap store shelf rack"))

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        if st.button(t.get("shelf_dialog_cancel", "Cancel"), use_container_width=True):
            st.session_state["show_shelf_cam"] = False
            st.rerun()

    with col_c2:
        if shelf_img is not None:
            if st.button(t.get("shelf_dialog_btn", "⚡ Inspect Movement"), type="primary", use_container_width=True):
                with st.spinner(t.get("shelf_dialog_analyzing", "AI scanning shelf brands and packet counts...")):
                    detected, err = audit_shelf_photo_with_ai(
                        shelf_img.getvalue(),
                        mime_type=shelf_img.type or "image/jpeg",
                        lang_name=current_lang_choice
                    )
                    if detected:
                        db.save_shelf_audit(current_store_phone, detected)

                        # Auto-update Inventory & KPI Metrics from Audit
                        if hasattr(db, "mark_items_as_stagnant_from_audit"):
                            flagged_count = db.mark_items_as_stagnant_from_audit(current_store_phone, detected)
                            if flagged_count > 0:
                                st.toast(f"🔄 Auto-flagged {flagged_count} stagnant items in Inventory & Dead Stock KPI!")

                        st.toast(t.get("shelf_audit_success", "Audit logged: Recognized {count} shelf products.").format(count=len(detected)))
                        st.session_state["show_shelf_cam"] = False
                        st.rerun()
                    else:
                        st.error(t.get("shelf_audit_failed", "Audit analysis failed: {err}").format(err=err))


# -------------------------------------------------------------
# 4. Authentication Flow (Login / Register)
# -------------------------------------------------------------
if not st.session_state.get("logged_in_store"):
    st.markdown(
        f"""
        <div class="kotak-header" style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 style="margin: 0; font-size: 24px; font-weight: 800;">{t['app_title']}</h1>
                <div class="kotak-header-sub">{t['app_tagline']}</div>
            </div>
            <div style="display: flex; align-items: center; justify-content: center;">
                {logo_html}
            </div>
        </div>
    """,
        unsafe_allow_html=True,
    )

    auth_choice = st.radio("Choose:", ["🔑 Login to Store", "📝 Register New Shop", "🔓 Forgot PIN?"], horizontal=True, label_visibility="collapsed")

    if auth_choice == "🔑 Login to Store":
        with st.form("login_box"):
            st.markdown("##### 🔑 Shopkeeper Login")
            l_phone = st.text_input("10-Digit Mobile Number", placeholder="e.g. 9822012345")
            l_pin = st.text_input("4-Digit Security PIN", type="password", max_chars=4, placeholder="****")
            l_remember = st.checkbox("Keep me signed in on this device", value=True)
            if st.form_submit_button("Access Dashboard", use_container_width=True, type="primary"):
                profile, error = db.verify_login(l_phone, l_pin)
                if profile:
                    st.session_state["logged_in_store"] = profile
                    if l_remember:
                        token = db.create_session(profile["phone_number"])
                        st.session_state["session_token"] = token
                        st.query_params["session"] = token
                    st.rerun()
                elif error == "LEGACY_NO_PIN":
                    st.warning("This account was created before PIN protection existed. Please use 'Forgot PIN?' to verify with OTP once and set a PIN.")
                else:
                    st.error(error or "Store not found. Please register first.")

    elif auth_choice == "📝 Register New Shop":
        st.markdown("##### 📝 Register Store Account")
        if "reg_otp" not in st.session_state:
            st.session_state["reg_otp"] = None
            st.session_state["temp_reg"] = {}

        r_shop = st.text_input("Store Name (दुकानाचे नाव)", placeholder="e.g. Patil Kirana Stores")
        r_owner = st.text_input("Owner Name (दुकानदाराचे नाव)", placeholder="e.g. Aniket Patil")
        r_phone = st.text_input("Mobile Number (मोबाईल नंबर)", placeholder="e.g. 9822012345")
        r_upi = st.text_input("Store UPI ID for receiving payments", placeholder="e.g. 9822012345@ybl")
        r_pin_col1, r_pin_col2 = st.columns(2)
        with r_pin_col1:
            r_pin = st.text_input("Create 4-Digit Security PIN", type="password", max_chars=4, placeholder="****")
        with r_pin_col2:
            r_pin_confirm = st.text_input("Confirm PIN", type="password", max_chars=4, placeholder="****")

        if st.button("📲 Send 4-Digit Verification Code", use_container_width=True):
            if not (r_shop and r_owner and r_phone and r_upi and r_pin and r_pin_confirm):
                st.error("Please fill in all store details, including your PIN.")
            elif not (r_pin.isdigit() and len(r_pin) == 4):
                st.error("PIN must be exactly 4 digits.")
            elif r_pin != r_pin_confirm:
                st.error("PINs do not match. Please re-enter.")
            else:
                otp = sms_service.generate_otp()
                st.session_state["reg_otp"] = otp
                st.session_state["temp_reg"] = {"shop_name": r_shop, "owner_name": r_owner, "phone_number": r_phone, "upi_id": r_upi, "pin": r_pin}
                sent_ok, msg = sms_service.send_sms_otp(r_phone, otp)
                st.success(f"✅ {msg}")

        if st.session_state.get("reg_otp"):
            with st.form("verify_box"):
                code = st.text_input("Enter 4-Digit Code", max_chars=4, placeholder="****")
                if st.form_submit_button("Verify & Activate Store", use_container_width=True, type="primary"):
                    if code.strip() == st.session_state["reg_otp"]:
                        d = st.session_state["temp_reg"]
                        success, err = db.register_shopkeeper(d["shop_name"], d["owner_name"], d["phone_number"], d["upi_id"], d["pin"])
                        if success:
                            profile = db.get_shopkeeper(d["phone_number"])
                            st.session_state["logged_in_store"] = profile
                            token = db.create_session(profile["phone_number"])
                            st.session_state["session_token"] = token
                            st.query_params["session"] = token
                            st.session_state["reg_otp"] = None
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(err)
                    else:
                        st.error("Invalid verification code.")

    else:
        st.markdown("##### 🔓 Reset Your PIN")
        if "recovery_otp" not in st.session_state:
            st.session_state["recovery_otp"] = None
            st.session_state["recovery_phone"] = None

        f_phone = st.text_input("10-Digit Mobile Number", placeholder="e.g. 9822012345", key="recovery_phone_input")

        if st.button("📲 Send OTP to Reset PIN", use_container_width=True):
            existing = db.get_shopkeeper(f_phone)
            if not existing:
                st.error("No store found with this mobile number.")
            else:
                otp = sms_service.generate_otp()
                st.session_state["recovery_otp"] = otp
                st.session_state["recovery_phone"] = f_phone
                sent_ok, msg = sms_service.send_sms_otp(f_phone, otp)
                st.success(f"✅ {msg}")

        if st.session_state.get("recovery_otp"):
            with st.form("recovery_box"):
                f_code = st.text_input("Enter OTP", max_chars=4, placeholder="****")
                f_pin1 = st.text_input("New 4-Digit PIN", type="password", max_chars=4, placeholder="****")
                f_pin2 = st.text_input("Confirm New PIN", type="password", max_chars=4, placeholder="****")
                if st.form_submit_button("Reset PIN", use_container_width=True, type="primary"):
                    if f_code.strip() != st.session_state["recovery_otp"]:
                        st.error("Invalid OTP.")
                    elif not (f_pin1.isdigit() and len(f_pin1) == 4):
                        st.error("PIN must be exactly 4 digits.")
                    elif f_pin1 != f_pin2:
                        st.error("PINs do not match. Please re-enter.")
                    else:
                        db.set_pin(st.session_state["recovery_phone"], f_pin1)
                        st.session_state["recovery_otp"] = None
                        st.success("✅ PIN reset! Please log in with your new PIN.")
                        st.rerun()
    st.stop()

# 5. Dashboard view
store = st.session_state["logged_in_store"]
store_phone = store["phone_number"]
shop_name = store["shop_name"]
owner_name = store["owner_name"]
shop_upi = store["upi_id"]

st.markdown(
    f"""
    <div class="kotak-header" style="display: flex; justify-content: space-between; align-items: center; padding: 16px 22px;">
        <div style="flex: 1; padding-right: 15px;">
            <h1 style="margin: 0; font-size: 22px; font-weight: 800; line-height: 1.2;">🏪 {shop_name}</h1>
            <div class="kotak-header-sub" style="margin-top: 4px; font-size: 13px;">
                {t['welcome_back']}, <b>{owner_name}</b><br>
                📞 +91 {store_phone}
            </div>
        </div>
        <div style="display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
            {logo_html}
        </div>
    </div>
""",
    unsafe_allow_html=True,
)
skus, capital, dead = db.get_kpi_metrics(store_phone)
total_udhar = db.get_total_udhar_pending(store_phone)

st.markdown(f"""
    <div class="kpi-grid">
        <div class="kotak-kpi-card">
            <div>
                <div class="kpi-card-title">📦 {t['kpi_skus']}</div>
                <div class="kpi-card-sub">Active catalog inventory</div>
            </div>
            <div class="kpi-card-amount">{skus} <span style="font-size:12px; font-weight:normal; opacity:0.75;">Items</span></div>
        </div>
        <div class="kotak-kpi-card">
            <div>
                <div class="kpi-card-title">💼 {t['kpi_capital']}</div>
                <div class="kpi-card-sub">Total stock purchase value</div>
            </div>
            <div class="kpi-card-amount">₹{capital:,.0f}</div>
        </div>
        <div class="kotak-kpi-card">
            <div>
                <div class="kpi-card-title">⏳ {t['kpi_dead']}</div>
                <div class="kpi-card-sub">Slow-moving stock estimate</div>
            </div>
            <div class="kpi-card-amount">₹{dead:,.0f}</div>
        </div>
        <div class="kotak-kpi-card accent-red">
            <div>
                <div class="kpi-card-title">🚨 {t['kpi_udhar']}</div>
                <div class="kpi-card-sub">Customer receivables pending</div>
            </div>
            <div class="kpi-card-amount red">₹{total_udhar:,.0f}</div>
        </div>
    </div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 🧭 6. SEGMENTED 2x2 ACTION BUTTON NAVIGATION
# -------------------------------------------------------------
if "active_nav" not in st.session_state:
    st.session_state["active_nav"] = "scan"

nav_row1_col1, nav_row1_col2 = st.columns(2)
with nav_row1_col1:
    btn_type = "primary" if st.session_state["active_nav"] == "scan" else "secondary"
    if st.button(t["tab_scan"], type=btn_type, use_container_width=True, key="nav_btn_scan"):
        st.session_state["active_nav"] = "scan"
        st.rerun()

with nav_row1_col2:
    btn_type = "primary" if st.session_state["active_nav"] == "inv" else "secondary"
    if st.button(t["tab_inventory"], type=btn_type, use_container_width=True, key="nav_btn_inv"):
        st.session_state["active_nav"] = "inv"
        st.rerun()

nav_row2_col1, nav_row2_col2 = st.columns(2)
with nav_row2_col1:
    btn_type = "primary" if st.session_state["active_nav"] == "udhar" else "secondary"
    if st.button(t["tab_udhar"], type=btn_type, use_container_width=True, key="nav_btn_udhar"):
        st.session_state["active_nav"] = "udhar"
        st.rerun()

with nav_row2_col2:
    btn_type = "primary" if st.session_state["active_nav"] == "radar" else "secondary"
    if st.button(t["tab_demand"], type=btn_type, use_container_width=True, key="nav_btn_radar"):
        st.session_state["active_nav"] = "radar"
        st.rerun()

st.write("")  # Visual spacing

# =============================================================
# VIEW 1: Vision OCR Bill Scan
# =============================================================
if st.session_state["active_nav"] == "scan":
    st.markdown(f"#### {t['upload_heading']}")
    st.caption(t["upload_sub"])

    input_mode = st.radio("Source:", ["📸 Phone Camera", "📁 Gallery File"], horizontal=True, label_visibility="collapsed")
    bill_img = st.camera_input("Take photo of wholesale receipt") if input_mode == "📸 Phone Camera" else st.file_uploader("Select Invoice Photo", type=["jpg", "png", "jpeg"])

    if bill_img is not None:
        file_type = bill_img.type if hasattr(bill_img, "type") and bill_img.type else "image/jpeg"
        file_id = getattr(bill_img, "name", "cam_snap")

        if "parsed_items" not in st.session_state or st.session_state.get("last_bill_id") != file_id:
            with st.spinner("⚡ Vision AI is analyzing invoice columns and items..."):
                extracted = extract_invoice_data_with_ai(bill_img.getvalue(), mime_type=file_type)
                clean = [
                    {
                        "Item Name": str(i.get("Item Name", "")),
                        "Quantity": int(i.get("Quantity", 1)),
                        "Rate (₹)": float(i.get("Rate (₹)", i.get("Rate", 0.0)))
                    }
                    for i in extracted
                ]
                st.session_state["parsed_items"] = clean
                st.session_state["last_bill_id"] = file_id

        items = st.session_state.get("parsed_items", [])
        if items:
            st.success(f"✅ Extracted {len(items)} line items from receipt.")
            st.caption(t["edit_instruction"])

            df_edit = st.data_editor(
                pd.DataFrame(items),
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "Item Name": st.column_config.TextColumn("Product SKU", required=True),
                    "Quantity": st.column_config.NumberColumn("Qty", min_value=1, step=1, required=True),
                    "Rate (₹)": st.column_config.NumberColumn("Unit Rate (₹)", min_value=0.0, step=1.0, format="₹%.2f", required=True)
                }
            )

            if st.button(f"✅ {t['save_stock_btn']}", use_container_width=True, type="primary"):
                db.add_or_update_stock(store_phone, df_edit.to_dict(orient="records"))
                st.balloons()
                st.toast(t["stock_updated_toast"])
                st.session_state["parsed_items"] = None
                st.rerun()

# =============================================================
# VIEW 2: Inventory View & Manual Entry
# =============================================================
elif st.session_state["active_nav"] == "inv":
    with st.expander(f"➕ {t['manual_add_heading']}"):
        with st.form("manual_stock_form"):
            col_m1, col_m2 = st.columns([2, 1])
            m_name = col_m1.text_input("Product Name", placeholder="e.g. Parle-G 100g")
            m_qty = col_m2.number_input("Quantity", min_value=1, step=1, value=10)
            m_rate = st.number_input("Wholesale Rate (₹)", min_value=1.0, step=5.0, value=25.0)

            if st.form_submit_button(t["add_item_btn"], use_container_width=True):
                if m_name:
                    db.add_or_update_stock(store_phone, [{"Item Name": m_name, "Quantity": m_qty, "Rate (₹)": m_rate}])
                    st.toast(f"Added {m_name} to inventory!")
                    st.rerun()
                else:
                    st.error("Please enter a product name.")

    search_q = st.text_input(t["search_stock"], placeholder="Search...", label_visibility="collapsed")
    df_inv = db.get_inventory_dataframe(store_phone)

    if not df_inv.empty:
        if search_q:
            df_inv = df_inv[df_inv["Item SKU"].str.contains(search_q, case=False, na=False)]
        st.dataframe(
            df_inv,
            use_container_width=True,
            column_config={
                "Rate (₹)": st.column_config.NumberColumn(format="₹%.2f"),
                "Total Capital (₹)": st.column_config.NumberColumn(format="₹%.2f")
            }
        )
    else:
        st.info(t["no_stock"])

# =============================================================
# VIEW 3: Udhar Ledger
# =============================================================
elif st.session_state["active_nav"] == "udhar":
    with st.expander(f"➕ {t['act_add_udhar']}"):
        with st.form("new_udhar_form"):
            u_name = st.text_input(t["customer_name"], placeholder="e.g. Ramesh Kulkarni")
            u_phone = st.text_input(t["customer_phone"], placeholder="e.g. 9822123456")
            u_amount = st.number_input(t["udhar_amount"], min_value=1.0, step=10.0, value=150.0)
            u_note = st.text_input(t["items_note"], placeholder="e.g. 1L Gemini Oil, 1kg Sugar")
            u_due = st.date_input(t["due_date"], min_value=date.today())

            if st.form_submit_button(t["save_udhar_btn"], use_container_width=True, type="primary"):
                if u_name and u_phone:
                    db.add_udhar_entry(store_phone, u_name, u_phone, u_amount, u_note, u_due)
                    st.success("Udhar record saved!")
                    st.rerun()
                else:
                    st.error("Please provide both name and phone number.")

    df_u = db.get_udhar_records(store_phone)
    pending_records = df_u[df_u["status"] != "Paid"] if not df_u.empty else pd.DataFrame()

    if not pending_records.empty:
        for _, row in pending_records.iterrows():
            st.markdown(f"""
                <div class="kotak-udhar-card">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <div class="kotak-udhar-title">👤 {row['customer_name']}</div>
                            <div class="kotak-udhar-sub">📞 +91 {row['customer_phone']} · 📅 Due: <b>{row['due_date']}</b></div>
                            <div class="kotak-udhar-note">📦 {row['items_note'] or 'Grocery Items'}</div>
                        </div>
                        <div style="font-size:19px; font-weight:800; color:#ED1C24;">₹{row['amount']:,.2f}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            col_qr, col_wa, col_settle = st.columns([1, 1.2, 1])
            upi_payload = f"upi://pay?pa={shop_upi}&pn={urllib.parse.quote(shop_name)}&am={row['amount']}&cu=INR&tn=Udhar_{row['id']}"

            with col_qr:
                qr = qrcode.QRCode(box_size=4, border=1)
                qr.add_data(upi_payload)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                with st.popover("📲 Scan QR"):
                    st.image(buf.getvalue(), caption=f"Pay ₹{row['amount']} to {shop_upi}")

            with col_wa:
                if lang_key == "mr":
                    msg = f"नमस्कार {row['customer_name']}जी, {shop_name} दुकानाची ₹{row['amount']} उधारी बाकी आहे (वस्तू: {row['items_note']}). देय तारीख: {row['due_date']}. थेट UPI द्वारे पैसे भरण्यासाठी लिंक: {upi_payload}"
                elif lang_key == "hi":
                    msg = f"नमस्ते {row['customer_name']}जी, {shop_name} की ₹{row['amount']} उधारी बाकी है (सामान: {row['items_note']}). अंतिम तिथि: {row['due_date']}. भुगतान लिंक: {upi_payload}"
                else:
                    msg = f"Dear {row['customer_name']}, reminder for pending store credit of ₹{row['amount']} at {shop_name}. Due Date: {row['due_date']}. Pay via UPI: {upi_payload}"

                wa_url = f"https://wa.me/91{row['customer_phone']}?text={urllib.parse.quote(msg)}"
                st.link_button(t["send_whatsapp_btn"], wa_url, use_container_width=True)

            with col_settle:
                if st.button(t["mark_paid_btn"], key=f"settle_{row['id']}", use_container_width=True):
                    db.settle_udhar(row["id"])
                    st.toast(f"Settled account for {row['customer_name']}!")
                    st.rerun()
    else:
        st.info(t["no_udhar"])

# =============================================================
# VIEW 4: Demand Radar & Dead Stock
# =============================================================
elif st.session_state["active_nav"] == "radar":
    st.markdown(f"#### {t['radar_heading']}")
    st.caption(t['radar_sub'])

    df_stock = db.get_inventory_dataframe(store_phone)

    if df_stock.empty:
        st.info(t['radar_no_items'])
    else:
        col_btn, col_info = st.columns([1, 2])
        with col_btn:
            run_forecast = st.button(t['radar_btn_run'], use_container_width=True, type="primary")

        raw_inventory = []
        for _, row in df_stock.iterrows():
            name = row.get("Item SKU") or row.get("Item Name") or row.get("item_name") or "Unknown Item"
            qty = (
                row.get("Quantity") or 
                row.get("Qty") or 
                row.get("qty") or 
                row.get("quantity") or 
                1
            )
            try:
                qty_int = int(qty)
            except (ValueError, TypeError):
                qty_int = 1
            raw_inventory.append({"item_name": str(name), "current_stock": qty_int})

        if run_forecast:
            with st.spinner(t['radar_analyzing']):
                results, error_msg = analyze_inventory_demand(
                    raw_inventory,
                    location="Maharashtra, India",
                    lang_name=lang_choice
                )
                st.session_state["demand_results"] = results
                st.session_state["demand_error"] = error_msg

        results = st.session_state.get("demand_results", [])
        error_msg = st.session_state.get("demand_error", None)

        if results:
            surges = [r for r in results if r.get("status") == "SURGE"]
            dead_stocks = [r for r in results if r.get("status") == "DEAD_STOCK"]

            st.markdown(f"""
                <div style="display:flex; gap:12px; margin-bottom:16px;">
                    <div style="flex:1; background-color:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.2); border-left:4px solid #ED1C24; border-radius:10px; padding:10px 14px;">
                        <span style="font-size:11px; font-weight:700; opacity:0.7;">{t['radar_surge_title']}</span>
                        <div style="font-size:20px; font-weight:800; color:#ED1C24;">{len(surges)} {t['radar_items_suffix']}</div>
                    </div>
                    <div style="flex:1; background-color:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.2); border-left:4px solid #D97706; border-radius:10px; padding:10px 14px;">
                        <span style="font-size:11px; font-weight:700; opacity:0.7;">{t['radar_dead_title']}</span>
                        <div style="font-size:20px; font-weight:800; color:#D97706;">{len(dead_stocks)} {t['radar_items_suffix']}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            status_labels = {
                "SURGE": t["radar_status_surge"],
                "DEAD_STOCK": t["radar_status_dead"],
                "STABLE": t["radar_status_stable"]
            }

            for item in results:
                status = item.get("status", "STABLE")
                badge_class = (
                    "badge-surge" if status == "SURGE"
                    else "badge-dead" if status == "DEAD_STOCK"
                    else "badge-stable"
                )
                border_color = (
                    "#ED1C24" if status == "SURGE"
                    else "#D97706" if status == "DEAD_STOCK"
                    else "#059669"
                )
                display_status = status_labels.get(status, status)

                st.markdown(f"""
                    <div class="kotak-udhar-card" style="border-left-color: {border_color} !important;">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
                            <span style="font-size:16px; font-weight:700; color:var(--text-color);">{item.get('item_name', '')}</span>
                            <span class="{badge_class}">{display_status}</span>
                        </div>
                        <div style="font-size:13px; color:var(--text-color); opacity:0.85; margin-bottom:4px;">
                            <b>{t['radar_signal_label']}:</b> {item.get('reason', '')}
                        </div>
                        <div style="font-size:13px; font-weight:600; color:{border_color};">
                            💡 {item.get('action', '')}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
        elif error_msg:
            st.error(f"⚠️ Error from Demand Engine: {error_msg}")

    # --- Visual Proof: Side-by-Side Shelf Audit Comparison ---
    st.divider()
    with st.expander(f"🖼️ {t.get('shelf_comp_heading', 'Shelf Rack Visual Proof & Audit History')}"):
        st.caption(t.get('shelf_comp_sub', 'Compare recent shelf scans to visually verify stagnant stock.'))

        if hasattr(db, "get_audit_comparison_pair"):
            latest_audit, prev_audit = db.get_audit_comparison_pair(store_phone)
        else:
            latest_audit, prev_audit = None, None

        if latest_audit and prev_audit:
            col_prev, col_latest = st.columns(2)

            with col_prev:
                st.markdown(f"**📅 {t.get('shelf_comp_prev', 'Previous Scan')}: {prev_audit['date']}**")
                st.caption(f"{len(prev_audit['items'])} {t.get('shelf_comp_items_found', 'items recognized')}")
                for itm in prev_audit["items"][:6]:
                    count_display = f" (~{itm.get('estimated_count', 1)} pcs)" if itm.get('estimated_count') else ""
                    st.markdown(f"- **{itm.get('item_name')}**{count_display}")

            with col_latest:
                st.markdown(f"**📅 {t.get('shelf_comp_latest', 'Latest Scan')}: {latest_audit['date']}**")
                st.caption(f"{len(latest_audit['items'])} {t.get('shelf_comp_items_found', 'items recognized')}")
                for itm in latest_audit["items"][:6]:
                    count_display = f" (~{itm.get('estimated_count', 1)} pcs)" if itm.get('estimated_count') else ""
                    st.markdown(f"- **{itm.get('item_name')}**{count_display}")
        else:
            st.info(t.get("shelf_comp_need_two", "Complete at least 2 shelf audits to unlock side-by-side movement tracking."))

    # --- Dead Stock Section ---
    st.divider()
    st.markdown(f"#### {t['dead_tab_heading']}")
    st.caption(t['dead_tab_sub'])

    dead_candidates = db.get_dead_stock_candidates(store_phone, days_threshold=30)
    if not dead_candidates:
        st.success(t['dead_no_items'])
    else:
        total_blocked = sum(item["capital_blocked"] for item in dead_candidates)

        st.markdown(f"""
            <div class="kotak-udhar-card" style="border-left-color: #D97706 !important;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="font-size:13px; font-weight:700; color:#D97706; text-transform:uppercase;">
                            {t['dead_blocked_val']}
                        </div>
                        <div style="font-size:12px; opacity:0.75;">{len(dead_candidates)} slow-moving products</div>
                    </div>
                    <div style="font-size:22px; font-weight:800; color:#D97706;">
                        ₹{total_blocked:,.0f}
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        if st.button(t['dead_action_btn'], use_container_width=True):
            with st.spinner("Calculating Kirana combo & clearance strategies..."):
                st.session_state["dead_stock_ai"] = generate_dead_stock_strategy(
                    dead_candidates, 
                    lang_name=lang_choice
                )

        strategies = st.session_state.get("dead_stock_ai", [])

        for item in dead_candidates:
            ai_info = next((s for s in strategies if s.get("item_name") == item["item_name"]), None)
            discount_badge = ai_info.get("discount_recommendation", "Suggested 5% Off") if ai_info else "Slow Mover"
            pitch_text = ai_info.get("pitch", "Place near counter to increase checkout visibility.") if ai_info else ""

            st.markdown(f"""
                <div class="kotak-udhar-card" style="border-left-color: #D97706 !important;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <div style="font-size:16px; font-weight:700;">📦 {item['item_name']}</div>
                            <div style="font-size:12px; opacity:0.75; margin-top:2px;">
                                Qty: <b>{item['quantity']}</b> · Blocked: <b>₹{item['capital_blocked']:,.0f}</b>
                            </div>
                        </div>
                        <span class="badge-dead">{discount_badge}</span>
                    </div>
                    <div style="margin-top:8px; padding-top:8px; border-top:1px dashed rgba(128,128,128,0.2); font-size:13px;">
                        <b>{t['dead_pitch_label']}:</b> <em>"{pitch_text}"</em>
                    </div>
                </div>
            """, unsafe_allow_html=True)

# -------------------------------------------------------------
# 📸 7. FLOATING CENTER SHELF SCANNER BUTTON (Kotak 811 FAB)
# -------------------------------------------------------------
if "show_shelf_cam" not in st.session_state:
    st.session_state["show_shelf_cam"] = False

# Floating Center Button Anchor
st.markdown('<div class="fab-dock">', unsafe_allow_html=True)
if st.button(t.get("fab_scan_label", "📸 Scan Shelf Rack"), key="btn_center_shelf_fab"):
    st.session_state["show_shelf_cam"] = True
st.markdown('</div>', unsafe_allow_html=True)

# Dialog Modal Call for Shelf Scan
if st.session_state.get("show_shelf_cam"):
    open_shelf_audit_dialog(store_phone, lang_choice)

# 8. Sidebar Configuration
with st.sidebar:
    st.markdown("### ⚙️ Store Profile Settings")

    with st.form("edit_profile_form"):
        st.caption("Update Store Details:")
        edit_sname = st.text_input("Store Name", value=shop_name)
        edit_oname = st.text_input("Owner Name", value=owner_name)
        edit_upi = st.text_input("Store UPI ID", value=shop_upi)

        if st.form_submit_button("💾 Save Profile Changes", use_container_width=True, type="primary"):
            if edit_sname and edit_oname and edit_upi:
                db.update_shopkeeper_profile(store_phone, edit_sname, edit_oname, edit_upi)
                st.session_state["logged_in_store"]["shop_name"] = edit_sname
                st.session_state["logged_in_store"]["owner_name"] = edit_oname
                st.session_state["logged_in_store"]["upi_id"] = edit_upi
                st.toast("Profile updated successfully!")
                st.rerun()
            else:
                st.error("Fields cannot be empty.")

    with st.expander("🔒 Change PIN"):
        with st.form("change_pin_form"):
            c_cur_pin = st.text_input("Current PIN", type="password", max_chars=4)
            c_new_pin1 = st.text_input("New PIN", type="password", max_chars=4)
            c_new_pin2 = st.text_input("Confirm New PIN", type="password", max_chars=4)
            if st.form_submit_button("Update PIN", use_container_width=True):
                verified, _ = db.verify_login(store_phone, c_cur_pin)
                if not verified:
                    st.error("Incorrect current PIN.")
                elif not (c_new_pin1.isdigit() and len(c_new_pin1) == 4):
                    st.error("PIN must be exactly 4 digits.")
                elif c_new_pin1 != c_new_pin2:
                    st.error("PINs do not match.")
                else:
                    db.set_pin(store_phone, c_new_pin1)
                    st.toast("✅ PIN updated!")

    st.divider()
    if st.button("🚪 Logout Store Account", use_container_width=True):
        db.delete_session(st.session_state.get("session_token"))
        st.session_state["logged_in_store"] = None
        st.session_state["session_token"] = None
        st.session_state["parsed_items"] = None
        st.query_params.clear()
        st.rerun()
