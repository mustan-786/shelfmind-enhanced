import streamlit as st
import os
from PIL import Image

logo_path = "logo.png"
if os.path.exists(logo_path):
    page_icon = Image.open(logo_path)
else:
    page_icon = "📦"

st.set_page_config(
    page_title="SHELF MIND",
    page_icon=page_icon,
    layout="centered",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------------------
# 🎨 GLOBAL THEME — fonts, gradient header, cards, badges
# -------------------------------------------------------------
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"]  {
        font-family: 'Poppins', sans-serif;
    }

    /* Hide default Streamlit chrome for a cleaner, app-like feel */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {background: rgba(0,0,0,0);}

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 3rem;
        max-width: 720px;
    }

    /* Gradient hero header */
    .sm-hero {
        background: linear-gradient(135deg, #0f766e 0%, #134e4a 55%, #0b3b36 100%);
        border-radius: 18px;
        padding: 22px 24px;
        margin-bottom: 18px;
        box-shadow: 0 8px 24px rgba(15, 118, 110, 0.25);
        display: flex;
        align-items: center;
        gap: 16px;
    }
    .sm-hero img {
        border-radius: 12px;
        width: 54px;
        height: 54px;
        object-fit: cover;
    }
    .sm-hero-title {
        color: #ffffff;
        font-size: 1.35rem;
        font-weight: 800;
        letter-spacing: 0.3px;
        margin: 0;
    }
    .sm-hero-sub {
        color: #b9f3e8;
        font-size: 0.85rem;
        margin: 2px 0 0 0;
    }

    /* KPI cards */
    .kpi-card {
        border-radius: 14px;
        padding: 14px 16px;
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-left: 4px solid var(--accent, #10b981);
        margin-bottom: 10px;
    }
    .kpi-label {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        opacity: 0.7;
        margin: 0;
    }
    .kpi-value {
        font-size: 1.5rem;
        font-weight: 700;
        margin: 2px 0 0 0;
    }

    /* Status badges */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
    }
    .badge-low { background: rgba(245, 158, 11, 0.18); color: #f59e0b; }
    .badge-dead { background: rgba(239, 68, 68, 0.18); color: #ef4444; }
    .badge-ok { background: rgba(16, 185, 129, 0.18); color: #10b981; }

    div.stButton > button, div.stFormSubmitButton > button {
        border-radius: 10px;
        font-weight: 600;
    }
    div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0f766e, #10b981);
        border: none;
    }
    </style>
""", unsafe_allow_html=True)

# Inject PWA Manifest for Mobile Shortcut Icon
st.markdown("""
    <link rel="manifest" href="manifest.json">
    <link rel="apple-touch-icon" href="logo.png">
    <meta name="apple-mobile-web-app-title" content="SHELF MIND">
    <meta name="application-name" content="SHELF MIND">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
""", unsafe_allow_html=True)

import pandas as pd
import urllib.parse
import qrcode
import io
from datetime import date
from translations import TRANSLATIONS
from ocr_pipeline import extract_invoice_data_with_ai
import database as db
import sms_service

db.init_db()


def render_hero():
    if os.path.exists(logo_path):
        import base64
        with open(logo_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        logo_html = f'<img src="data:image/png;base64,{b64}" />'
    else:
        logo_html = '<div style="font-size:2.2rem;">📦</div>'

    st.markdown(f"""
        <div class="sm-hero">
            {logo_html}
            <div>
                <p class="sm-hero-title">SHELF MIND</p>
                <p class="sm-hero-sub">Shopkeeper Intelligence &amp; Kirana Operations</p>
            </div>
        </div>
    """, unsafe_allow_html=True)


render_hero()

# Language Selector
lang_choice = st.selectbox(
    "🌐 Language / भाषा निवडा / भाषा चुनें",
    ["English", "मराठी (Marathi)", "हिंदी (Hindi)"],
    index=0
)
lang_key = "mr" if "Marathi" in lang_choice else "hi" if "Hindi" in lang_choice else "en"
t = TRANSLATIONS[lang_key]

# -------------------------------------------------------------
# 🔄 SESSION RESTORE — a random session token lives in the URL,
# never the phone number or PIN, so refresh-persistence can't be
# used to skip authentication.
# -------------------------------------------------------------
query_params = st.query_params
session_token = query_params.get("session", None)

if "logged_in_store" not in st.session_state or st.session_state["logged_in_store"] is None:
    if session_token:
        restored = db.get_store_by_session(session_token)
        if restored:
            st.session_state["logged_in_store"] = restored
            st.session_state["session_token"] = session_token
        else:
            st.query_params.clear()

# -------------------------------------------------------------
# 🏪 SHOPKEEPER LOGIN, REGISTRATION & PIN RECOVERY
# -------------------------------------------------------------
if not st.session_state.get("logged_in_store"):
    st.subheader(t["login_heading"])

    auth_mode = st.radio(
        t["auth_mode_label"],
        [t["auth_login"], t["auth_register"], f"🔓 {t['forgot_pin']}"],
        horizontal=True
    )

    # ---------- LOGIN (phone + PIN) ----------
    if auth_mode == t["auth_login"]:
        with st.form("login_form"):
            phone_input = st.text_input(t["mobile_label"], placeholder="e.g. 9822012345")
            pin_input = st.text_input(t["pin_label"], type="password", max_chars=4, placeholder="****")
            remember_me = st.checkbox("Keep me signed in on this device", value=True)
            submit_login = st.form_submit_button(t["login_btn"], use_container_width=True, type="primary")

            if submit_login:
                profile, error = db.verify_login(phone_input, pin_input)
                if profile:
                    st.session_state["logged_in_store"] = profile
                    if remember_me:
                        token = db.create_session(profile["phone_number"])
                        st.session_state["session_token"] = token
                        st.query_params["session"] = token
                    st.toast(f"Welcome back, {profile['shop_name']}!")
                    st.rerun()
                elif error == "LEGACY_NO_PIN":
                    st.warning(t["legacy_pin_setup"])
                else:
                    st.error(error or t["wrong_pin"])

    # ---------- REGISTER (with OTP + PIN setup) ----------
    elif auth_mode == t["auth_register"]:
        if "reg_otp" not in st.session_state:
            st.session_state["reg_otp"] = None
            st.session_state["temp_reg_data"] = {}

        st.markdown(f"### {t['auth_register']}")
        new_shop = st.text_input("Store Name (दुकानाचे नाव)", placeholder="e.g. Patil Super Shoppe")
        new_owner = st.text_input("Owner Name (दुकानदाराचे नाव)", placeholder="e.g. Aniket Patil")
        new_phone = st.text_input(t["mobile_label"], placeholder="e.g. 9822012345")
        new_upi = st.text_input("Store UPI ID for Receiving Money (उदा. yourname@oksbi / 9822012345@ybl)", placeholder="e.g. 9822012345@ybl")

        col_pin1, col_pin2 = st.columns(2)
        with col_pin1:
            new_pin = st.text_input(t["set_pin_label"], type="password", max_chars=4, placeholder="****")
        with col_pin2:
            new_pin_confirm = st.text_input(t["confirm_pin_label"], type="password", max_chars=4, placeholder="****")

        if st.button("📲 Send 4-Digit OTP on Mobile", use_container_width=True):
            if not (new_shop and new_owner and new_phone and new_upi and new_pin and new_pin_confirm):
                st.error("Please fill in all shop details, including your PIN, before requesting OTP.")
            elif not (new_pin.isdigit() and len(new_pin) == 4):
                st.error("PIN must be exactly 4 digits.")
            elif new_pin != new_pin_confirm:
                st.error(t["pin_mismatch"])
            else:
                generated_otp = sms_service.generate_otp()
                st.session_state["reg_otp"] = generated_otp
                st.session_state["temp_reg_data"] = {
                    "shop_name": new_shop,
                    "owner_name": new_owner,
                    "phone_number": new_phone,
                    "upi_id": new_upi,
                    "pin": new_pin
                }
                sent_ok, msg = sms_service.send_sms_otp(new_phone, generated_otp)
                if sent_ok:
                    st.success(f"✅ {msg}")
                else:
                    st.warning(f"⚠️ {msg}")

        if st.session_state.get("reg_otp"):
            with st.form("otp_verification_form"):
                entered_otp = st.text_input("Enter 4-Digit OTP received on SMS", max_chars=4, placeholder="****")
                verify_btn = st.form_submit_button("Verify OTP & Complete Registration", use_container_width=True, type="primary")

                if verify_btn:
                    if entered_otp.strip() == st.session_state["reg_otp"]:
                        d = st.session_state["temp_reg_data"]
                        success, err = db.register_shopkeeper(d["shop_name"], d["owner_name"], d["phone_number"], d["upi_id"], d["pin"])
                        if success:
                            profile = db.get_shopkeeper(d["phone_number"])
                            st.session_state["logged_in_store"] = profile
                            token = db.create_session(profile["phone_number"])
                            st.session_state["session_token"] = token
                            st.query_params["session"] = token
                            st.session_state["reg_otp"] = None
                            st.balloons()
                            st.success("🎉 Store verified & registered successfully!")
                            st.rerun()
                        else:
                            st.error(err)
                    else:
                        st.error("❌ Invalid OTP. Please enter the correct 4-digit code.")

    # ---------- FORGOT PIN (re-verify via OTP, then set a new PIN) ----------
    else:
        st.markdown(f"### 🔓 {t['forgot_pin']}")
        if "recovery_otp" not in st.session_state:
            st.session_state["recovery_otp"] = None
            st.session_state["recovery_phone"] = None

        recovery_phone = st.text_input(t["mobile_label"], placeholder="e.g. 9822012345", key="recovery_phone_input")

        if st.button("📲 Send OTP to Reset PIN", use_container_width=True):
            existing = db.get_shopkeeper(recovery_phone)
            if not existing:
                st.error(t["no_store_found"])
            else:
                generated_otp = sms_service.generate_otp()
                st.session_state["recovery_otp"] = generated_otp
                st.session_state["recovery_phone"] = recovery_phone
                sent_ok, msg = sms_service.send_sms_otp(recovery_phone, generated_otp)
                if sent_ok:
                    st.success(f"✅ {msg}")
                else:
                    st.warning(f"⚠️ {msg}")

        if st.session_state.get("recovery_otp"):
            with st.form("recovery_form"):
                entered_otp = st.text_input("Enter OTP", max_chars=4, placeholder="****")
                r_pin1 = st.text_input(t["set_pin_label"], type="password", max_chars=4, placeholder="****")
                r_pin2 = st.text_input(t["confirm_pin_label"], type="password", max_chars=4, placeholder="****")
                reset_btn = st.form_submit_button("Reset PIN", use_container_width=True, type="primary")

                if reset_btn:
                    if entered_otp.strip() != st.session_state["recovery_otp"]:
                        st.error("❌ Invalid OTP.")
                    elif not (r_pin1.isdigit() and len(r_pin1) == 4):
                        st.error("PIN must be exactly 4 digits.")
                    elif r_pin1 != r_pin2:
                        st.error(t["pin_mismatch"])
                    else:
                        db.set_pin(st.session_state["recovery_phone"], r_pin1)
                        st.session_state["recovery_otp"] = None
                        st.success("✅ PIN reset! Please log in with your new PIN.")
                        st.rerun()

    st.stop()

# -------------------------------------------------------------
# 🎯 ACTIVE STORE DASHBOARD (Logged In & Isolated)
# -------------------------------------------------------------
current_store = st.session_state["logged_in_store"]
store_phone = current_store["phone_number"]
shop_name = current_store["shop_name"]
owner_name = current_store["owner_name"]
shop_upi = current_store["upi_id"]

# --- SIDEBAR PROFILE & SETTINGS ---
st.sidebar.markdown(f"### 🏪 **{shop_name}**")
st.sidebar.caption(f"👤 Owner: **{owner_name}**")
st.sidebar.caption(f"📞 Registered Mobile: `+91 {store_phone}`")
st.sidebar.info(f"💳 Active UPI: `{shop_upi}`")

with st.sidebar.expander("⚙️ Edit Store Details"):
    with st.form("edit_profile_form"):
        updated_shop_name = st.text_input("Store Name (दुकानाचे नाव)", value=shop_name)
        updated_owner_name = st.text_input("Owner Name (मालकाचे नाव)", value=owner_name)
        updated_upi = st.text_input("Store UPI ID (पेमेंटसाठी UPI)", value=shop_upi)

        save_changes = st.form_submit_button("💾 Save Profile Changes", use_container_width=True, type="primary")

        if save_changes:
            if updated_shop_name and updated_owner_name and updated_upi:
                db.update_shopkeeper_profile(store_phone, updated_shop_name, updated_owner_name, updated_upi)
                st.session_state["logged_in_store"]["shop_name"] = updated_shop_name
                st.session_state["logged_in_store"]["owner_name"] = updated_owner_name
                st.session_state["logged_in_store"]["upi_id"] = updated_upi
                st.toast("✅ Store details updated successfully!")
                st.rerun()
            else:
                st.error("Please fill in all fields.")

with st.sidebar.expander("🔒 Change PIN"):
    with st.form("change_pin_form"):
        cur_pin = st.text_input("Current PIN", type="password", max_chars=4)
        new_pin_a = st.text_input("New PIN", type="password", max_chars=4)
        new_pin_b = st.text_input("Confirm New PIN", type="password", max_chars=4)
        change_pin_btn = st.form_submit_button("Update PIN", use_container_width=True)

        if change_pin_btn:
            verified, _ = db.verify_login(store_phone, cur_pin)
            if not verified:
                st.error(t["wrong_pin"])
            elif not (new_pin_a.isdigit() and len(new_pin_a) == 4):
                st.error("PIN must be exactly 4 digits.")
            elif new_pin_a != new_pin_b:
                st.error(t["pin_mismatch"])
            else:
                db.set_pin(store_phone, new_pin_a)
                st.toast("✅ PIN updated!")

if st.sidebar.button(t["logout_btn"], use_container_width=True):
    db.delete_session(st.session_state.get("session_token"))
    st.session_state["logged_in_store"] = None
    st.session_state["session_token"] = None
    st.session_state["parsed_items"] = None
    st.query_params.clear()
    st.rerun()

# Dynamic KPI Metrics Isolated to this Shopkeeper
total_skus, total_capital, dead_capital, low_stock_count = db.get_kpi_metrics(store_phone)
total_udhar = db.get_total_udhar_pending(store_phone)

st.title(f"📱 {shop_name}")
st.caption(f"{t['app_subtitle']}")


def kpi_card(label, value, accent="#10b981"):
    st.markdown(f"""
        <div class="kpi-card" style="--accent:{accent}">
            <p class="kpi-label">{label}</p>
            <p class="kpi-value">{value}</p>
        </div>
    """, unsafe_allow_html=True)


k1, k2 = st.columns(2)
with k1:
    kpi_card(t["total_skus"], f"{total_skus} SKUs", "#10b981")
with k2:
    kpi_card(t["working_capital"], f"₹{total_capital:,.0f}", "#0ea5e9")

k3, k4 = st.columns(2)
with k3:
    kpi_card(t["low_stock_kpi"], f"{low_stock_count} items", "#f59e0b")
with k4:
    kpi_card(t["total_udhar"], f"₹{total_udhar:,.0f}", "#ef4444")

st.divider()

tab1, tab2, tab3, tab4 = st.tabs([t["tab_upload"], t["tab_stock"], t["tab_alerts"], t["tab_udhar"]])

# --- TAB 1: Invoice Vision Ingestion + Human-In-The-Loop Grid ---
with tab1:
    st.subheader(t["upload_heading"])
    input_mode = st.radio("Capture Method:", ["📸 Open Phone Camera", "📁 Upload from Gallery"], horizontal=True)
    image_file = st.camera_input("Take photo of wholesale bill") if input_mode == "📸 Open Phone Camera" else st.file_uploader(t["upload_btn"], type=["jpg", "png", "jpeg"])

    if image_file is not None:
        file_type = image_file.type if hasattr(image_file, "type") and image_file.type else "image/jpeg"
        file_id = getattr(image_file, "name", "cam_snap")

        if "parsed_items" not in st.session_state or st.session_state.get("last_up") != file_id:
            with st.spinner("⚡ Vision AI is analyzing invoice layout..."):
                extracted = extract_invoice_data_with_ai(image_file.getvalue(), mime_type=file_type)
                clean = [
                    {
                        "Item Name": str(i.get("Item Name", "")),
                        "Quantity": int(i.get("Quantity", 1)),
                        "Rate (₹)": float(i.get("Rate (₹)", i.get("Rate", 0.0)))
                    }
                    for i in extracted
                ]
                st.session_state["parsed_items"] = clean
                st.session_state["last_up"] = file_id

        items = st.session_state.get("parsed_items", [])
        if items:
            st.success(t["upload_success"])
            st.info(t["edit_instruction"])

            df_edit = st.data_editor(
                pd.DataFrame(items),
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "Item Name": st.column_config.TextColumn("Product SKU", required=True),
                    "Quantity": st.column_config.NumberColumn("Qty", min_value=1, step=1, required=True),
                    "Rate (₹)": st.column_config.NumberColumn("Rate (₹)", min_value=0.0, step=0.5, format="₹%.2f", required=True)
                }
            )

            if st.button(f"✅ {t['save_stock_btn']}", use_container_width=True, type="primary"):
                db.add_or_update_stock(store_phone, df_edit.to_dict(orient="records"))
                st.balloons()
                st.success(t["stock_updated_toast"])
                st.session_state["parsed_items"] = None
                st.rerun()
        else:
            st.warning("No items were detected in that image. Try a clearer photo, or add items manually in the Live Inventory tab.")

# --- TAB 2: Live Real-Time Stock Table (search + delete) ---
with tab2:
    st.subheader(t["tab_stock"])
    df_live = db.get_inventory_dataframe(store_phone)

    if not df_live.empty:
        search_query = st.text_input(t["search_placeholder"], label_visibility="collapsed", placeholder=t["search_placeholder"])
        filtered = df_live[df_live["Item SKU"].str.contains(search_query, case=False, na=False)] if search_query else df_live

        st.dataframe(filtered, use_container_width=True, hide_index=True)

        with st.expander(f"🗑️ {t['delete_item_btn']} an item"):
            item_to_delete = st.selectbox("Select item to remove", options=df_live["Item SKU"].tolist())
            if st.button(t["delete_item_btn"], use_container_width=True):
                db.delete_inventory_item(store_phone, item_to_delete)
                st.toast(f"Removed {item_to_delete} from inventory.")
                st.rerun()
    else:
        st.info(t["no_stock_yet"])

# --- TAB 3: Demand Radar & Stock Health Alerts ---
with tab3:
    st.subheader(t["tab_alerts"])

    st.markdown(f"#### {t['low_stock_heading']}")
    low_stock_df = db.get_low_stock_items(store_phone)
    if not low_stock_df.empty:
        st.dataframe(low_stock_df, use_container_width=True, hide_index=True)
    else:
        st.success(t["no_low_stock"])

    st.markdown("#### 🔴 Dead / At-Risk Stock")
    dead_df = db.get_dead_stock_items(store_phone)
    if not dead_df.empty:
        st.dataframe(dead_df, use_container_width=True, hide_index=True)
        st.caption(f"₹{dead_capital:,.0f} of working capital is currently locked in slow-moving stock.")
    else:
        st.success(t["no_dead_stock"])

    st.info(t["weather_alert"])

# --- TAB 4: Udhar (Credit) Ledger & Real NPCI UPI Payments / WhatsApp Reminders ---
with tab4:
    st.subheader(t["tab_udhar"])

    with st.expander(t["add_udhar_btn"]):
        with st.form("new_udhar_form"):
            c_name = st.text_input(t["customer_name"])
            c_phone = st.text_input(t["phone_number"], placeholder="e.g. 9822123456")
            c_amount = st.number_input(t["udhar_amount"], min_value=1.0, step=10.0, value=250.0)
            c_items = st.text_input(t["items_taken"], placeholder="e.g. 1L Oil, 1kg Sugar")
            c_due = st.date_input(t["due_date"], min_value=date.today())

            if st.form_submit_button(t["save_udhar"], use_container_width=True):
                if c_name and c_phone:
                    clean_phone = c_phone.replace("+91", "").replace(" ", "").strip()
                    db.add_udhar_entry(store_phone, c_name, clean_phone, c_amount, c_items, c_due)
                    st.success("Udhar entry saved!")
                    st.rerun()
                else:
                    st.error("Please enter both customer name and mobile number.")

    df_udhar = db.get_udhar_records(store_phone)
    pending_udhar = df_udhar[df_udhar["status"] != "Paid"] if not df_udhar.empty else df_udhar

    if not pending_udhar.empty:
        show_paid = st.toggle("Show settled (paid) records too", value=False)
        display_df = df_udhar if show_paid else pending_udhar

        for idx, row in display_df.iterrows():
            with st.container(border=True):
                col_info, col_actions = st.columns([2, 1])

                with col_info:
                    status_badge = '<span class="badge badge-ok">Paid</span>' if row["status"] == "Paid" else '<span class="badge badge-low">Pending</span>'
                    st.markdown(f"**👤 {row['customer_name']}** {status_badge} (📞 `+91 {row['customer_phone']}`)", unsafe_allow_html=True)
                    st.markdown(f"💰 **Amount Due:** ₹{row['amount']:,.2f} | 📅 **Due Date:** `{row['due_date']}`")
                    if row["items_note"]:
                        st.caption(f"Items Taken: {row['items_note']}")

                with col_actions:
                    if row["status"] != "Paid":
                        upi_payload = f"upi://pay?pa={shop_upi}&pn={urllib.parse.quote(shop_name)}&am={row['amount']}&cu=INR&tn=Udhar_{row['id']}"

                        qr = qrcode.QRCode(box_size=4, border=1)
                        qr.add_data(upi_payload)
                        qr.make(fit=True)
                        img_qr = qr.make_image(fill_color="black", back_color="white")
                        buf = io.BytesIO()
                        img_qr.save(buf, format="PNG")

                        with st.expander("📲 Scan UPI QR"):
                            st.image(buf.getvalue(), caption=f"Scan to Pay ₹{row['amount']} to {shop_upi}", width=150)

                        if lang_key == "mr":
                            msg = f"नमस्कार {row['customer_name']}जी, {shop_name} दुकानाची ₹{row['amount']} उधारी बाकी आहे (वस्तू: {row['items_note']}). देय तारीख: {row['due_date']}. थेट UPI द्वारे पैसे भरण्यासाठी लिंक: {upi_payload}"
                        elif lang_key == "hi":
                            msg = f"नमस्ते {row['customer_name']}जी, {shop_name} की ₹{row['amount']} उधारी बकाया है (सामान: {row['items_note']}). अंतिम तिथि: {row['due_date']}. UPI भुगतान लिंक: {upi_payload}"
                        else:
                            msg = f"Dear {row['customer_name']}, reminder for pending store credit of ₹{row['amount']} at {shop_name}. Due Date: {row['due_date']}. Pay via UPI: {upi_payload}"

                        wa_url = f"https://wa.me/91{row['customer_phone']}?text={urllib.parse.quote(msg)}"
                        st.link_button("📲 Send WhatsApp", wa_url, use_container_width=True)

                        if st.button(t["mark_paid"], key=f"settle_{row['id']}", use_container_width=True):
                            db.settle_udhar(row["id"])
                            st.toast(f"Payment settled for {row['customer_name']}!")
                            st.rerun()
    else:
        st.info("No pending Udhar records for this store.")
