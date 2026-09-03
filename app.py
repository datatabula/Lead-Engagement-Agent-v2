import re
import html as html_module
import streamlit.components.v1 as components
import streamlit as st
from models import LEAInput
from pipeline import run_pipeline

INDENT = "        "   # 8 spaces = one indent level. Change this to make indents deeper or shallower everywhere at once.

def format_contact_lines(contact):
    lines = [f"{INDENT}name: {contact.name}"]
    if contact.name_romanized:
        lines.append(f"    name_romanized: {contact.name_romanized}")
    if contact.role_title:
        lines.append(f"    role_title: {contact.role_title}")
    if contact.department:
        lines.append(f"    department: {contact.department}")
    if contact.contact_url_or_email:
        lines.append(f"    contact_url_or_email: {contact.contact_url_or_email}")
    if contact.email:
        lines.append(f"    email: {contact.email}")
    if contact.email_source:
        lines.append(f"    email_source: {contact.email_source}")
    if contact.phone:
        lines.append(f"    phone: {contact.phone}")
    if contact.linkedin_url:
        lines.append(f"    linkedin_url: {contact.linkedin_url}")
    if contact.source_url and contact.source_url != contact.linkedin_url:
        lines.append(f"    source_url: {contact.source_url}")
    return lines


def editable_with_copy(label, text, box_id):
    escaped = html_module.escape(text or "")
    components.html(f"""
        <div style="font-family: sans-serif;">
            <div style="font-size: 13px; margin-bottom: 4px; color: #888;">{label}</div>
            <textarea id="{box_id}" style="width: 100%; height: 420px; font-family: monospace; font-size: 14px; padding: 8px; box-sizing: border-box;">{escaped}</textarea>
            <button onclick="navigator.clipboard.writeText(document.getElementById('{box_id}').value)" style="margin-top: 6px; padding: 4px 12px; cursor: pointer;">📋 Copy</button>
        </div>
    """, height=480)

def build_readable_output(ep, lea_input) -> str:
    lines = []
    lines.append("--- Engagement Plan ---")
    lines.append(f"Company: {ep.company_name_jp} | {ep.company_name_en}")
    lines.append(f"Industry: {ep.industry}")

    lines.append("")
    lines.append("Primary contact:")
    if ep.primary_contact:
        lines.extend(format_contact_lines(ep.primary_contact))
    else:
        lines.append(f"{INDENT}None - addressed to a role/department instead")

    if ep.backup_contacts:
        lines.append("")
        lines.append(f"Backup contacts ({len(ep.backup_contacts)}):")
        for i, b in enumerate(ep.backup_contacts):
            if i > 0:
                lines.append("")
            lines.extend(format_contact_lines(b))

    if ep.general_inquiry_url:
        lines.append("")
        lines.append(f"General inquiry URL: {ep.general_inquiry_url}")

    if ep.signals_found:
        lines.append("")
        lines.append("Signals found:")
        for i, signal in enumerate(ep.signals_found, start=1):
            lines.append(f"{INDENT}{i}. {signal.name}")
            lines.append(f"{INDENT * 2}evidence: {signal.evidence_url}")

    lines.append("")
    lines.append(f"Engagement type: {ep.engagement_type}")
    lines.append(f"Outreach method: {lea_input.method}")

    lines.append("")
    lines.append("Personalization (levels with usable content):")
    personalization_levels = [
        ("warm", ep.personalization.warm),
        ("distant_connection", ep.personalization.distant_connection),
        ("agents_research", ep.personalization.agents_research),
        ("buying_signal", ep.personalization.buying_signal),
        ("position_rapport", ep.personalization.position_rapport),
        ("company_rapport", ep.personalization.company_rapport),
        ("industry_rapport", ep.personalization.industry_rapport),
    ]
    for level_name, level_data in personalization_levels:
        if level_data.availability:
            lines.append(f"{INDENT}{level_name}:")
            lines.append(f"{INDENT * 2}content: {level_data.content}")
            if level_data.evidence_url:
                lines.append(f"{INDENT * 2}evidence: {level_data.evidence_url}")

    if ep.likely_objections:
        lines.append("")
        lines.append("Likely objections:")
        for obj in ep.likely_objections:
            lines.append(f"{INDENT}- {obj.objection}")
            lines.append(f"{INDENT * 2}reason: {obj.reason}")

    lines.append("")
    lines.append(f"CTA: {ep.cta}")
    if ep.recommended_contact_time:
        lines.append(f"Recommended contact time: {ep.recommended_contact_time}")

    if ep.other_recommended_next_actions:
        lines.append("")
        lines.append("Other recommended next actions:")
        parts = [p.strip() for p in ep.other_recommended_next_actions.split(". ") if p.strip()]
        for i, part in enumerate(parts, start=1):
            if not part.endswith("."):
                part += "."
            lines.append(f"{INDENT}{i}. {part}")

    return "\n".join(lines)

def build_html_output(ep, lea_input) -> str:
    plain = build_readable_output(ep, lea_input)
    html_lines = []
    for line in plain.split("\n"):
        stripped = line.lstrip(" ")
        leading_spaces = len(line) - len(stripped)
        escaped = html_module.escape(stripped)
        linked = re.sub(
            r'(https?://[^\s<]+)',
            r'<a href="\1" target="_blank">\1</a>',
            escaped
        )
        html_lines.append("&nbsp;" * leading_spaces + linked)
    return "<br>".join(html_lines)

def copy_button_for_text(text: str, key: str):
    js_safe = text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
    components.html(f"""
        <button onclick="navigator.clipboard.writeText(`{js_safe}`)"
                style="padding: 4px 12px; cursor: pointer; margin-top: 8px;">
            📋 Copy Engagement Plan
        </button>
    """, height=50)

st.title("LEA v2")

st.markdown("""
    <style>
    input::placeholder, textarea::placeholder {
        font-style: italic;
    }
    </style>
""", unsafe_allow_html=True)

def enforce_dont_know_exclusivity(key):
    current = set(st.session_state[key])
    previous = set(st.session_state.get(key + "_prev", []))
    newly_added = current - previous

    if "Don't know" in newly_added:
        st.session_state[key] = ["Don't know"]
    elif "Don't know" in current and len(current) > 1:
        st.session_state[key] = [opt for opt in st.session_state[key] if opt != "Don't know"]

    st.session_state[key + "_prev"] = list(st.session_state[key])

if "leav2_output" not in st.session_state:
    st.session_state.leav2_output = None
if "leav2_used_input" not in st.session_state:
    st.session_state.leav2_used_input = None

with st.sidebar:
    st.title("LEA v2")
    st.header("Today, I'm messaging...")

    company = st.text_input("Company name", placeholder="Unabbreviate the company, give full names")

    found_contact = st.text_area(
        "Contact name",
        placeholder="藏田 亮祐 or Ryosuke Kurata"
    )

    st.write("Any of these buying signals seem to apply?")
    signal_options = [
        "Engineers present in company",
        "Hiring international talent",
        "Seeking bilinguals",
        "Seeking foreigners",
        "\"Foreigners welcome\" job postings",
        "Seeking English or Japanese qualifications",
        "New HR person",
        "Don't know"
    ]
    selected_signals = st.pills(
        "Select known signals",
        options=signal_options,
        selection_mode="multi",
        default=["Don't know"],
        key="selected_signals",
        on_change=enforce_dont_know_exclusivity,
        args=("selected_signals",),
        label_visibility="collapsed"
    )

    know_him = st.radio(
        "Do you know them?",
        options=["Yes", "I might know someone", "No"],
        index=2
    )

    warm = None
    distant_connection_who = None

    if know_him == "Yes":
        engagement_type = "warm"
        warm = st.text_input("Who?", placeholder="who?", label_visibility="collapsed")
    elif know_him == "I might know someone":
        engagement_type = "distant_connection"
        distant_connection_who = st.text_input("Who?", placeholder="who?", label_visibility="collapsed")
    else:
        engagement_type_labels = {
            "1st_touch_no_connection": "first time to contact them",
            "2nd_touch_no_connection": "second time to contact them"
        }
        st.write("It would be my:")
        engagement_type = st.selectbox(
            "Engagement type",
            options=["1st_touch_no_connection", "2nd_touch_no_connection"],
            index=0,
            format_func=lambda x: engagement_type_labels[x],
            label_visibility="collapsed"
        )

    st.write("know what would build rapport with them?")

    rapport_categories = st.pills(
        "Rapport categories",
        options=["Position", "Company", "Industry", "Don't know"],
        selection_mode="multi",
        default=["Don't know"],
        key="rapport_categories",
        on_change=enforce_dont_know_exclusivity,
        args=("rapport_categories",),
        label_visibility="collapsed"
    )

    rapport_position = st.text_input("Position rapport", placeholder="new HR head got hired", label_visibility="collapsed") if "Position" in rapport_categories else None
    rapport_company = st.text_input("Company rapport", placeholder="company's contract with X is ending", label_visibility="collapsed") if "Company" in rapport_categories else None
    rapport_industry = st.text_input("Industry rapport", placeholder="insurance industry aggressively growing", label_visibility="collapsed") if "Industry" in rapport_categories else None

    st.write("Know their likely objection?")
    objection_options = ["no budget", "not urgent", "already have provider", "too busy", "not priority", "Don't know"]
    selected_objections = st.pills(
        "Objections",
        options=objection_options,
        selection_mode="multi",
        default=["Don't know"],
        key="selected_objections",
        on_change=enforce_dont_know_exclusivity,
        args=("selected_objections",),
        label_visibility="collapsed"
    )

    col1, col2 = st.columns(2)
    with col1:
        method = st.selectbox("Outreach method", options=["linkedin", "email"], index=0)
    with col2:
        i_am = st.selectbox("Sending as", options=["marc", "john", "kasumi", "yoshie"], index=0)

    calendly = st.checkbox("Include Calendly link")

# --- Build the actual LEAInput from the human-friendly sidebar answers ---
buying_signals_list = [s for s in selected_signals if s != "Don't know"]
likely_objection_list = [o for o in selected_objections if o != "Don't know"]

try:
    lea_input = LEAInput(
        found_contact=found_contact or None,
        found_buying_signal=None,
        lead_name=None,
        company=company,
        engagement_type=engagement_type,
        warm=warm,
        rapport_position=rapport_position,
        rapport_company=rapport_company,
        rapport_industry=rapport_industry,
        likely_objection=likely_objection_list,
        buying_signals=buying_signals_list,
        i_am=i_am,
        method=method,
        calendly=calendly,
        more_context=None
    )
    brief_json = lea_input.model_dump_json(indent=2, ensure_ascii=False)
    brief_error = None
except Exception as e:
    lea_input = None
    brief_json = None
    brief_error = str(e)

if st.session_state.leav2_output is None:
    col_middle, col_right = st.columns(2)

    with col_middle:
        st.subheader("Research brief (LEAInput)")
        if brief_error:
            st.error(brief_error)
        else:
            st.code(brief_json, language="json")

        generate_clicked = st.button("Research and Strategize for me")

        if generate_clicked and lea_input is not None:
            with st.spinner("Researching and building your engagement plan may take a minute..."):
                try:
                    st.session_state.leav2_output = run_pipeline(lea_input)
                    st.session_state.leav2_used_input = lea_input
                    st.rerun()
                except Exception as e:
                    st.error(f"Something went wrong: {e}")

    with col_right:
        st.subheader("Engagement Plan")
        st.write("Fill out the research brief and click the button to generate.")

else:
    st.subheader("Engagement Plan")

    if st.button("← Edit brief again"):
        st.session_state.leav2_output = None
        st.rerun()

    output = st.session_state.leav2_output
    used_input = st.session_state.leav2_used_input

    st.markdown(
    f'<div style="font-family: monospace; font-size: 14px;">{build_html_output(output.engagement_plan, used_input)}</div>',
    unsafe_allow_html=True
)

    copy_button_for_text(build_readable_output(output.engagement_plan, used_input), "engagement_plan_copy")

    with st.expander("Show raw JSON"):
        st.code(output.engagement_plan.model_dump_json(indent=2, ensure_ascii=False), language="json")

    if output.research_findings is not None:
        with st.expander("🔍 See the research"):
            st.code(output.research_findings.model_dump_json(indent=2, ensure_ascii=False), language="json")
    else:
        st.caption("This engagement plan came from cache, so no fresh research ran this time — nothing new to show here.")

    st.subheader("Proposed Messages")

    method_label = {"linkedin": "LinkedIn", "email": "Email"}.get(used_input.method, used_input.method.capitalize())

    for i, message in enumerate(output.messages, start=1):
        st.markdown(f"**{method_label} version {i}**")
        col_jp, col_en = st.columns(2)
        with col_jp:
            editable_with_copy("Japanese", message.japanese, f"msg_{i}_jp")
        with col_en:
            editable_with_copy("English", message.english, f"msg_{i}_en")