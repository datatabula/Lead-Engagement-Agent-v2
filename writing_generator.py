from typing import Optional
from anthropic import Anthropic
from dotenv import load_dotenv

from models import EngagementPlan, WritingOutput, WrittenMessage, LEAInput, LEAv2Output
from lookup_tables import MESSAGE_RULES, SIGNATORIES
from writing_prompt import JP_SYSTEM_PROMPT, EN_SYSTEM_PROMPT
from loggers import log_api_cost

load_dotenv()
client = Anthropic()

JP_CHAR_RATIO = 1.7
MAX_SHORTEN_ATTEMPTS = 2


def count_english_words(text: str) -> int:
    return len(text.split())


def count_japanese_chars(text: str) -> int:
    return len(text)


def japanese_over_limit(text: str, hard_max_words: int) -> bool:
    return count_japanese_chars(text) > int(hard_max_words * JP_CHAR_RATIO)


def english_over_limit(text: str, hard_max_words: int) -> bool:
    return count_english_words(text) > hard_max_words


def shorten_text(text: str, length_description: str, lead_id: str, call_type: str, run_id=None) -> str:
    shorten_prompt = f"""This message is too long. Shorten it while keeping the same meaning, rapport point, and CTA - do not add new content.

Current version ({length_description}):
{text}
"""
    response = client.messages.create(
        model="claude-haiku-4-5",   # ← changed from "claude-sonnet-5"
        max_tokens=1024,
        tools=[{
            "name": "raw_shortened_text",
            "description": "Record the shortened text",
            "input_schema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"]
            }
        }],
        tool_choice={"type": "tool", "name": "raw_shortened_text"},
        messages=[{"role": "user", "content": shorten_prompt}]
    )

    log_api_cost(
        run_id=run_id,
        lead_id=lead_id,
        call_type=call_type,
        model="claude-haiku-4-5",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens
    )

    return response.content[0].input["text"]

def preview(text: str, length: int = 60) -> str:
    return text if len(text) <= length else text[:length] + "..."

def run_writing(engagement_plan: EngagementPlan, lea_input: LEAInput, run_id=None) -> WritingOutput:
    rules = MESSAGE_RULES.get((lea_input.method, engagement_plan.engagement_type))

    if rules is None:
        raise RuntimeError(
            f"No MESSAGE_RULES entry for (method={lea_input.method}, engagement_type={engagement_plan.engagement_type}). "
            "Add an entry to MESSAGE_RULES for this combination."
        )

    lead_id = f"{lea_input.company} | {lea_input.lead_name or 'unknown'}"

    # --- Step 1: write the Japanese messages (source of truth) ---
    jp_char_min = int(rules["ideal_min"] * JP_CHAR_RATIO)
    jp_char_max = int(rules["ideal_max"] * JP_CHAR_RATIO)
    jp_char_hard_max = int(rules["hard_max"] * JP_CHAR_RATIO)

    jp_user_message = f"""EngagementPlan:
{engagement_plan.model_dump_json(indent=2, ensure_ascii=False)}

Length rules for this lead (method={lea_input.method}, engagement_type={engagement_plan.engagement_type}):
Ideal length: roughly {jp_char_min}-{jp_char_max} Japanese characters
Hard max: roughly {jp_char_hard_max} Japanese characters
Additional notes: {rules['notes']}
{"Also write subject_lines_jp - one Japanese email subject line per message, following the email subject line rules in your system prompt." if lea_input.method == "email" else ""}
"""

    jp_response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=3072,
        system=JP_SYSTEM_PROMPT,
        tools=[{
            "name": "raw_japanese_output",
            "description": "Record the two Japanese message drafts, and their subject lines if this is an email.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "messages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 2
                    },
                    "subject_lines_jp": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 2,
                        "description": "Only include this field if method is 'email'. One subject line per message, in the same order as messages. Omit this field entirely if method is not 'email'."
                    }
                },
                "required": ["messages"]
            }
        }],
        tool_choice={"type": "tool", "name": "raw_japanese_output"},
        messages=[{"role": "user", "content": jp_user_message}]
    )

    log_api_cost(
        run_id=run_id,
        lead_id=lead_id,
        call_type="run_writing_jp",
        model="claude-sonnet-5",
        input_tokens=jp_response.usage.input_tokens,
        output_tokens=jp_response.usage.output_tokens
    )

    if jp_response.stop_reason == "max_tokens":
        print("--- WARNING: Japanese writing call hit max_tokens and was likely truncated. ---")

    raw_jp_messages = jp_response.content[0].input.get("messages", [])
    raw_subject_lines_jp = jp_response.content[0].input.get("subject_lines_jp", [])

    valid_jp = [m for m in raw_jp_messages if m.strip()]

    if len(valid_jp) < 2:
        raise RuntimeError(f"Expected 2 Japanese messages from Claude, got {len(valid_jp)} usable. Raw response: {raw_jp_messages}")

    if len(valid_jp) > 2:
        print(f"--- WARNING: Claude returned {len(valid_jp)} Japanese messages instead of 2, using the first 2. Raw response: {raw_jp_messages} ---")
        valid_jp = valid_jp[:2]

    if lea_input.method == "email" and len(raw_subject_lines_jp) < 2:
        print(f"--- WARNING: method is 'email' but fewer than 2 subject_lines_jp were returned. Raw response: {raw_subject_lines_jp} ---")

    if engagement_plan.engagement_type == "1st_touch_no_connection":
        if "メルカリ" not in valid_jp[0]:
            print(f"--- WARNING: rule 14's cold-outreach opening (apology/self-intro/social-proof) is missing from message 1. Message 1: {preview(valid_jp[0])} ---")
        if "メルカリ" in valid_jp[1]:
            print(f"--- WARNING: rule 14's cold-outreach content appeared in message 2, which should never include it. Message 2: {preview(valid_jp[1])} ---")
    else:
        if "メルカリ" in valid_jp[0]:
            print(f"--- WARNING: rule 14's Mercari social-proof content appeared in message 1, but engagement_type is not 1st_touch_no_connection - it should never appear outside that case. Message 1: {preview(valid_jp[0])} ---")
        if "メルカリ" in valid_jp[1]:
            print(f"--- WARNING: rule 14's Mercari social-proof content appeared in message 2, but engagement_type is not 1st_touch_no_connection - it should never appear outside that case. Message 2: {preview(valid_jp[1])} ---")

    def mentions_company(text: str) -> bool:
        if engagement_plan.company_name_jp and engagement_plan.company_name_jp in text:
            return True
        if engagement_plan.company_name_en.split()[0] in text:
            return True
        if engagement_plan.engagement_type == "warm" and "御社" in text:
            return True
        return False

    if not mentions_company(valid_jp[0]):
        print(f"--- WARNING: message 1 does not appear to mention the company name (rule 16). Message 1: {preview(valid_jp[0])} ---")
    if not mentions_company(valid_jp[1]):
        print(f"--- WARNING: message 2 does not appear to mention the company name (rule 16). Message 2: {preview(valid_jp[1])} ---")

    for i, jp_text in enumerate(valid_jp):
        attempts = 0
        while japanese_over_limit(jp_text, rules["hard_max"]) and attempts < MAX_SHORTEN_ATTEMPTS:
            jp_text = shorten_text(jp_text, f"{count_japanese_chars(jp_text)} characters, limit {jp_char_hard_max}", lead_id, "shorten_jp", run_id)
            attempts += 1
        if japanese_over_limit(jp_text, rules["hard_max"]):
            print(f"--- WARNING: Japanese message {i + 1} is still over the length limit after {MAX_SHORTEN_ATTEMPTS} shorten attempts. May need manual trimming. ---")
        valid_jp[i] = jp_text

    # --- Step 2: adapt each Japanese message into English ---
    english_messages = []
    subject_en_list = []

    for i, jp_text in enumerate(valid_jp):
        subject_jp_for_this_message = raw_subject_lines_jp[i] if lea_input.method == "email" and i < len(raw_subject_lines_jp) else None

        en_user_message = f"""Japanese message to adapt into English (message {i + 1} of 2):
{jp_text}

English length rule for this lead: ideal {rules['ideal_min']}-{rules['ideal_max']} words, hard max {rules['hard_max']} words.
"""
        if subject_jp_for_this_message:
            en_user_message += f"\nJapanese subject line to adapt into an English subject line (subject_en): {subject_jp_for_this_message}\n"

        en_response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1024,
            system=EN_SYSTEM_PROMPT,
            tools=[{
                "name": "raw_english_output",
                "description": "Record the English adaptation of this one message, and its subject line if this is an email.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "english": {"type": "string"},
                        "subject_en": {
                            "type": "string",
                            "description": "Only include this field if a Japanese subject line was given to adapt. Omit entirely otherwise."
                        }
                    },
                    "required": ["english"]
                }
            }],
            tool_choice={"type": "tool", "name": "raw_english_output"},
            messages=[{"role": "user", "content": en_user_message}]
        )

        log_api_cost(
            run_id=run_id,
            lead_id=lead_id,
            call_type="run_writing_en",
            model="claude-sonnet-5",
            input_tokens=en_response.usage.input_tokens,
            output_tokens=en_response.usage.output_tokens
        )

        if en_response.stop_reason == "max_tokens":
            print(f"--- WARNING: English adaptation call for message {i + 1} hit max_tokens. ---")

        en_text = en_response.content[0].input.get("english", "").strip()
        subject_en = en_response.content[0].input.get("subject_en")

        if lea_input.method != "email":
            subject_en = None

        if subject_jp_for_this_message and not subject_en:
            print(f"--- WARNING: a Japanese subject line was given for message {i + 1}, but no subject_en came back. ---")

        attempts = 0
        while english_over_limit(en_text, rules["hard_max"]) and attempts < MAX_SHORTEN_ATTEMPTS:
            en_text = shorten_text(en_text, f"{count_english_words(en_text)} words, limit {rules['hard_max']}", lead_id, "shorten_en", run_id)
            attempts += 1
        if english_over_limit(en_text, rules["hard_max"]):
            print(f"--- WARNING: English message {i + 1} is still over the length limit after {MAX_SHORTEN_ATTEMPTS} shorten attempts. May need manual trimming. ---")

        english_messages.append(en_text)
        subject_en_list.append(subject_en)
    
    signature = SIGNATORIES[lea_input.i_am]

    valid_jp = [f"{jp}\n\n{signature['jp']}" for jp in valid_jp]
    english_messages = [f"{en}\n\n{signature['en']}" for en in english_messages]

    return WritingOutput(messages=[
        WrittenMessage(
            japanese=jp,
            english=en,
            subject_jp=(raw_subject_lines_jp[i] if lea_input.method == "email" and i < len(raw_subject_lines_jp) else None),
            subject_en=subject_en_list[i]
        )
        for i, (jp, en) in enumerate(zip(valid_jp, english_messages))
    ])


def format_contact(contact) -> str:
    lines = [f"    name: {contact.name}"]
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
    return "\n".join(lines)


def print_readable_output(leav2_output: LEAv2Output, lea_input: LEAInput) -> None:
    ep = leav2_output.engagement_plan

    print("\n--- Engagement Plan ---")
    print(f"Company: {ep.company_name_jp} | {ep.company_name_en}")
    print(f"Industry: {ep.industry}")

    print("\nPrimary contact:")
    if ep.primary_contact:
        print(format_contact(ep.primary_contact))
    else:
        print("    None - addressed to a role/department instead)")

    if ep.backup_contacts:
        print(f"\nBackup contacts ({len(ep.backup_contacts)}):")
        for b in ep.backup_contacts:
            print(format_contact(b))
            print()

    if ep.general_inquiry_url:
        print(f"General inquiry URL: {ep.general_inquiry_url}")

    if ep.signals_found:
        print("\nSignals found:")
        for i, signal in enumerate(ep.signals_found, start=1):
            print(f"  {i}. {signal.name}")
            print(f"     evidence: {signal.evidence_url}")

    print(f"\nEngagement type: {ep.engagement_type}")
    print(f"Outreach method: {lea_input.method}")

    print("\nPersonalization (levels with usable content):")
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
            print(f"  {level_name}:")
            print(f"    content: {level_data.content}")
            if level_data.evidence_url:
                print(f"    evidence: {level_data.evidence_url}")

    if ep.likely_objections:
        print("\nLikely objections:")
        for obj in ep.likely_objections:
            print(f"  - {obj.objection}")
            print(f"    reason: {obj.reason}")

    print(f"\nCTA: {ep.cta}")

    if ep.recommended_contact_time:
        print(f"Recommended contact time: {ep.recommended_contact_time}")

    if ep.other_recommended_next_actions:
        print("\nOther recommended next actions:")
        parts = [p.strip() for p in ep.other_recommended_next_actions.split(". ") if p.strip()]
        for i, part in enumerate(parts, start=1):
            if not part.endswith("."):
                part += "."
            print(f"  {i}. {part}")

    print("\nMessage strategies:")
    for i, strat in enumerate(ep.message_strategies, start=1):
        print(f"  Message {i}:")
        print(f"    personalization level: {strat.chosen_personalization_level}")
        print(f"    rapport content: {strat.rapport_content}")


    print("\n--- Proposed Messages ---")
    for i, msg in enumerate(leav2_output.messages, start=1):
        print(f"\nMessage {i}:")
        if msg.subject_jp:
            print(f"  Subject (JP): {msg.subject_jp}")
        if msg.subject_en:
            print(f"  Subject (EN): {msg.subject_en}")
        print(f"  JP: {msg.japanese}")
        print(f"  EN: {msg.english}")



if __name__ == "__main__":
    from models import LEAInput
    from pre_research import build_preresearch_context
    from pipeline import get_research_findings, merge_all_research
    from strategy_generator import build_engagement_plan

    test_input = LEAInput(
        company="株式会社村田製作所",
        lead_name="Okuda Hiroyuki",
        method="linkedin",
        engagement_type="1st_touch_no_connection"
    )

    pre_context = build_preresearch_context(test_input.lead_name, test_input.company)
    research_findings = get_research_findings(test_input.lead_name, test_input.company)
    hierarchy = merge_all_research(test_input, pre_context, research_findings)

    engagement_plan = build_engagement_plan(test_input, hierarchy, research_findings)
    writing_output = run_writing(engagement_plan, test_input)

    leav2_output = LEAv2Output(engagement_plan=engagement_plan, messages=writing_output.messages)

    print_readable_output(leav2_output, test_input)