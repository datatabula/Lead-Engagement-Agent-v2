# strategy_generator.py flow
#
# Purpose — call Claude once to produce a full EngagementPlan for one lead.
# No tools/search here (unlike research_agent.py) — pure judgment over data
# we already have, so it's a single structured call.
#
# Input — lea_input, hierarchy (from merge_all_research), research_findings.
# Logic — bundle all 3 into one user message → call Claude with SYSTEM_PROMPT
#         + the raw_strategy tool (forced, since it's the only tool) →
#         parse the raw_strategy tool_use block into an EngagementPlan.
# Output — one EngagementPlan.
# Failure case — same known gap as run_research: returns None if Claude
#         never calls raw_strategy. Not solved yet.
# Test — run with real merged data and inspect the result.

from models import EngagementPlan
from dotenv import load_dotenv
from anthropic import Anthropic
from strategy_prompt import SYSTEM_PROMPT
from lookup_tables import CONTACT_WINDOWS, POSITION_RAPPORT, COMPANY_RAPPORT, INDUSTRY_RAPPORT
from models import FoundContact
from loggers import log_api_cost
from models import EngagementPlan, LikelyObjection

tools = [
    {
        "name": "raw_strategy",
        "description": "Record the finished engagement plan once your analysis is complete",
        "input_schema": EngagementPlan.model_json_schema()
    }
]
tool_choice = { "type": "tool", "name": "raw_strategy"}

load_dotenv()
client = Anthropic()

#*contact_lists means "accept any number of arguments, and pack them all into one tuple." 
#merge_contacts([1, 2], [3], [4, 5, 6])
# prints: ([1, 2], [3], [4, 5, 6])
#contact_lists is a tuple (a list of lists, namely found_backups, 
#engagement_plan.backup_contacts, and research_backups)
def merge_contacts(*contact_lists):     
    combined = []
    seen = set()
    for contact_list in contact_lists:
        for contact in contact_list:
            key = contact.name or contact.name_romanized or contact.contact_url_or_email
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            combined.append(contact)
    return combined

def compute_likely_objections(engagement_plan, competitor_it_was_found_under):
    matched_categories = {
        strategy.matched_rapport_category
        for strategy in engagement_plan.message_strategies
        if strategy.matched_rapport_category
    }

    objections = []

    if competitor_it_was_found_under:
        objections.append(LikelyObjection(
            objection="Already has a provider",
            reason=f"Target company was found as a client under {competitor_it_was_found_under}."
        ))
    elif "Internal Language Training" in matched_categories:
        objections.append(LikelyObjection(
            objection="Already has a provider",
            reason="Internal Language Training detected"
        ))

    if "M&A / Integration" in matched_categories:
        objections.append(LikelyObjection(
            objection="No budget",
            reason="Companies undergoing M&A / Integration usually no budget"
        ))

    if engagement_plan.industry == "IT / SaaS":
        objections.append(LikelyObjection(
            objection="Too busy",
            reason="IT/SaaS usually busy"
        ))

    return objections

def merge_objections(*objection_lists, limit=3):
    combined = []
    seen = set()
    for objection_list in objection_lists:
        for obj in objection_list:
            if obj.objection not in seen:
                seen.add(obj.objection)
                combined.append(obj)
    return combined[:limit]

def build_engagement_plan(lea_input, hierarchy, research_findings, run_id=None, found_contact=None, competitor_it_was_found_under=None):

    response = client.messages.create(
        model = "claude-sonnet-5",
        max_tokens = 4096,
        system = SYSTEM_PROMPT,
        tools = tools,
        tool_choice = tool_choice,
        messages = [
            {
                "role" : "user",
                "content" : f"""Lead input: {lea_input.model_dump_json(indent=2, ensure_ascii=False)}

                Personalization Hierarchy : {hierarchy.model_dump_json(indent=2, ensure_ascii=False)}

               Research findings : {research_findings.model_dump_json(indent=2, ensure_ascii=False) if research_findings is not None else 'None - no research findings were available (the research agent may not have completed successfully)'}

                Found contact (already verified by a separate contact-finding pipeline - use this ONLY 
                to judge whether a specific named person was already found, for point 11's other_recommended_next_actions 
                decision; primary_contact/backup_contacts/company names are handled separately in code, 
                not by you): {found_contact.model_dump_json(indent=2, ensure_ascii=False) if found_contact is not None else 'None - no pre-found contact was supplied'}
            
                Human-typed contact note (NOT verified, NOT structured data - a free-text note a human
                typed directly, e.g. "Talked to Sarah in HR, she's the recruiter." Use it the same way
                as the Found contact field above, when judging whether a contact is already known - but
                treat anything mentioned here as unconfirmed, not verified fact.): {found_contact_note if found_contact_note is not None else 'None - no human-typed contact note was supplied'}"""
            
            }
        ]
    )

    lead_id = f"{lea_input.company} | {lea_input.lead_name or 'unknown'}"
    log_api_cost(
        run_id=run_id,
        lead_id=lead_id,
        call_type="building the ep",
        model="claude-sonnet-5",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "raw_strategy":

            engagement_plan = EngagementPlan(**block.input)

            # --- buying_signal is always human-typed input in v1 (merge_all_research
            # never populates it from research_agent), so its evidence is never a
            # real URL - override whatever the LLM guessed here with the truth.
            if engagement_plan.personalization.buying_signal.availability:
                engagement_plan.personalization.buying_signal.evidence_url = "human input"

            # --- found_contact overrides: verified data always wins over LLM guesswork ---
            if found_contact is not None:
                if found_contact.company_name_japanese:
                    engagement_plan.company_name_jp = found_contact.company_name_japanese
                if found_contact.company_name_english:
                    engagement_plan.company_name_en = found_contact.company_name_english
                if found_contact.official_website:
                    engagement_plan.general_inquiry_url = found_contact.official_website
                if found_contact.primary_contact:
                    engagement_plan.primary_contact = found_contact.primary_contact

            # --- backup contacts: found_contact's verified list first, then
            # whatever the LLM itself produced, then research_agent's
            # opportunistic finds - deduplicated by name along the way
            found_backups = found_contact.backup_contacts if found_contact else []
            research_backups = research_findings.backup_contacts if research_findings else []
            engagement_plan.backup_contacts = merge_contacts(
                found_backups,
                engagement_plan.backup_contacts,
                research_backups
            )
            # --- primary contact must never be empty when backups exist -
            # promote the first backup (already the most-trusted one, since
            # merge_contacts puts found_contact's verified backups first) to
            # primary, and remove it from backups so it isn't listed twice.
            if engagement_plan.primary_contact is None and engagement_plan.backup_contacts:
                engagement_plan.primary_contact = engagement_plan.backup_contacts.pop(0)

            engagement_plan.likely_objections = merge_objections(
                compute_likely_objections(engagement_plan, competitor_it_was_found_under),
                engagement_plan.likely_objections
            )

            if engagement_plan.contact_role_category != "HR, HRBP, L&D, talent development":
                engagement_plan.cta = "forward_me"

            engagement_plan.recommended_contact_time = CONTACT_WINDOWS.get(
                engagement_plan.contact_role_category, "Anytime during business hours"
            )

            engagement_plan.recommended_contact_time = CONTACT_WINDOWS[contact_role_category]
            if engagement_plan.other_recommended_next_actions:
                engagement_plan.other_recommended_next_actions += " Reasonable additional time to spend researching this target is 15 mins max."

            RAPPORT_LOOKUP_BY_LEVEL = {
                "position_rapport": POSITION_RAPPORT,
                "company_rapport": COMPANY_RAPPORT,
                "industry_rapport": INDUSTRY_RAPPORT,
            }

            for strategy in engagement_plan.message_strategies:
                if strategy.matched_rapport_category:
                    lookup_table = RAPPORT_LOOKUP_BY_LEVEL[strategy.chosen_personalization_level]
                    strategy.rapport_content = lookup_table[strategy.matched_rapport_category]["en"]

            return engagement_plan

if __name__ == "__main__":
    from pprint import pprint
    from models import LEAInput
    from pre_research import build_preresearch_context
    from pipeline import get_research_findings, merge_all_research

    test_input = LEAInput(
        company="Panasonic Holdings Corporation",
        lead_name="Tatsuo Kinoshita"
    )

    pre_context = build_preresearch_context(test_input.lead_name, test_input.company)
    research_findings = get_research_findings(test_input.lead_name, test_input.company)
    hierarchy = merge_all_research(test_input, pre_context, research_findings)

    engagement_plan = build_engagement_plan(test_input, hierarchy, research_findings)
    pprint(engagement_plan.model_dump(), sort_dicts=False)