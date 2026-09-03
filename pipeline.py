# pipeline.py flow
#
# Foreseeable steps for this file:
# 1. Cache-skip orchestration                  - DONE
# 2. Full personalization hierarchy resolution - DONE
# 3. Calling the Strategy call                 - DONE (wired in, not yet test-confirmed end-to-end)
# 4. Calling the Writing call                  - run_writing() itself is built and tested in
#                                                 writing_generator.py, just not yet wired into run_pipeline
# 5. Handling the known failure case           - not yet solved (see run_research note below)
# 6. Logging                                   - not yet built
# 7. Final output assembly                     - not yet built (no combined "Contact-Ready Lead
#                                                 Master JSON" step yet - run_pipeline just returns
#                                                 the bare EngagementPlan)
#
# --- Map of what's in this file, top to bottom ---
#
# get_research_findings(lead_name, company).       The cache-skip decision
# merge_all_research(lea_input, pre_context, research_findings)
       # merges all research and makes 7 levels
#
# parse_buying_signal(raw_text)
# parse_found_contact(raw_text)       human pasted or typed info > makes it json
#
# resolve_final_lead(lea_input, found_contact)
#
# run_pipeline(lea_input)
#   The orchestrator - Parses found_contact, resolves final_lead, builds pre_context + research_findings
#   + hierarchy,  calls build_engagement_plan, returns the finished EngagementPlan.
#
# Test - run against a company/lead with no cache entry (fresh path), then
# again with the same pair (cache-hit path), to confirm both work. Also
# test with and without a found_contact to confirm the override logic
# actually kicks in.
from pre_research import build_preresearch_context
from research_agent import run_research
import json
from pydantic import ValidationError
from models import LEAInput, PersonalizationHierarchy, FoundContact, BuyingSignalData, LEAv2Output
from strategy_generator import build_engagement_plan
from writing_generator import run_writing
import uuid
from ep_cache import get_cached_plan, store_plan



def get_research_findings(lead_name, company, run_id=None):
    pre_context = build_preresearch_context(lead_name, company)

    if pre_context.has_cached_research is not None:
        return pre_context.has_cached_research

    return run_research(lead_name, company, run_id)


from models import LEAInput, PersonalizationHierarchy

def merge_all_research(lea_input, pre_context, research_findings):
    # start with a completely blank hierarchy — all 7 levels unavailable by default
    hierarchy = PersonalizationHierarchy()

    # level 1: warm prev interaction
    if lea_input.warm is not None:
        hierarchy.warm.availability = True
        hierarchy.warm.content = lea_input.warm

    # level 2: distant connection
    if pre_context.has_distant_cxn:
        hierarchy.distant_connection.availability = True

        lines = []
        for match in pre_context.has_distant_cxn:
            line = f"{lea_input.company}  |  {match.contact.name}  |  known by {match.whose_connection}"
            lines.append(line)
        hierarchy.distant_connection.content = "\n".join(lines)

    # level 3: agent's research (person-level specifically — per the doc, this
    # level is about what the agent found about the PERSON, not the company)
    # research_findings can be None (e.g. we haven't run the agent in this test),
    # so always check that first before touching anything inside it
    if research_findings is not None and research_findings.person_lvl_findings:
        hierarchy.agents_research.availability = True

        lines = []
        for finding in research_findings.person_lvl_findings:
            if finding.evidence_url:
                lines.append(f"{finding.content} (source: {finding.evidence_url})")
            else:
                lines.append(finding.content)
        hierarchy.agents_research.content = "\n".join(lines)

    # level 4: LDA v1 buying signal — can come from the raw found_buying_signal
    # text (JSON or manually typed) and/or the buying_signals checkbox list;
    # either one being present is enough to count as available
    if lea_input.found_buying_signal is not None or lea_input.buying_signals:
        hierarchy.buying_signal.availability = True

        parts = []
        if lea_input.found_buying_signal is not None:
            parts.append(lea_input.found_buying_signal)
        if lea_input.buying_signals:
            parts.append(", ".join(lea_input.buying_signals))
        hierarchy.buying_signal.content = " | ".join(parts)

    # level 5: general position rapport
    # for now this only checks the human's manual override (the "I know
    # something about their position" text box). The static lookup-table
    # fallback — matching the contact's actual role to one of the 10 canned
    # position categories from your doc — isn't built yet. That's a bigger,
    # separate step (it needs its own matching logic, similar to how we
    # matched company names) — flagging it, not solving it in this pass.
    if lea_input.rapport_position is not None:
        hierarchy.position_rapport.availability = True
        hierarchy.position_rapport.content = lea_input.rapport_position

    # level 6: general company rapport — same idea, human override only for now
    if lea_input.rapport_company is not None:
        hierarchy.company_rapport.availability = True
        hierarchy.company_rapport.content = lea_input.rapport_company

    # level 7: general industry rapport — same idea, human override only for now
    if lea_input.rapport_industry is not None:
        hierarchy.industry_rapport.availability = True
        hierarchy.industry_rapport.content = lea_input.rapport_industry

    # hand back the fully (or partially) filled-in hierarchy
    return hierarchy


def parse_buying_signal(raw_text):
    try:
        parsed = json.loads(raw_text)
        return BuyingSignalData(**parsed)
    except (json.JSONDecodeError, TypeError):
        return raw_text


def parse_found_contact(raw_text):
    try:
        parsed = json.loads(raw_text)
        return FoundContact(**parsed)
    except (json.JSONDecodeError, TypeError, ValidationError):
        return raw_text

# Decides which name to actually treat as "the lead" for research
#   purposes. Prefers the real, verified name found_contact.primary_contact
#   already has (romanized first), and only falls back to whatever
#   lea_input.lead_name was originally submitted with if there's no
#   found_contact.
def resolve_final_lead(lea_input, found_contact):
    if isinstance(found_contact, FoundContact) and found_contact.primary_contact:
        primary = found_contact.primary_contact
        if primary.name_romanized:
            return primary.name_romanized
        if primary.name:
            return primary.name
    return lea_input.lead_name


def run_pipeline(lea_input):
    run_id = str(uuid.uuid4())

    cached_plan = get_cached_plan(lea_input)
    research_findings = None

    if cached_plan is not None:
        engagement_plan = cached_plan
    else:
        found_contact = None
        found_contact_note = None
        if lea_input.found_contact is not None:
            parsed = parse_found_contact(lea_input.found_contact)
            if isinstance(parsed, FoundContact):
                found_contact = parsed
            else:
                found_contact_note = parsed

        final_lead = resolve_final_lead(lea_input, found_contact)

        pre_context = build_preresearch_context(final_lead, lea_input.company)
        research_findings = get_research_findings(final_lead, lea_input.company, run_id)
        hierarchy = merge_all_research(lea_input, pre_context, research_findings)

        engagement_plan = build_engagement_plan(
            lea_input, hierarchy, research_findings, run_id,
            found_contact=found_contact,
            found_contact_note=found_contact_note,
            competitor_it_was_found_under=pre_context.competitor_it_was_found_under
        )

        store_plan(lea_input, engagement_plan)

    writing_output = run_writing(engagement_plan, lea_input, run_id)

    return LEAv2Output(
        engagement_plan=engagement_plan,
        messages=writing_output.messages,
        research_findings=research_findings
    )

if __name__ == "__main__":
    # a throwaway LEAInput just for testing — company is required, everything else
    # can stay at its default except warm, which we're deliberately filling in
    # so we can confirm level 1 actually turns "available"
    test_input = LEAInput(
        company="Panasonic Holdings Corporation",
        lead_name="Tatsuo Kinoshita",
        warm="introduced at a networking event",
        found_buying_signal="Company posted a job listing requiring English proficiency",
        buying_signals=["have engineers", "currently hiring foreigners"],
        rapport_position="recently promoted to VP",
        rapport_company="company just signed a new international contract",
        rapport_industry="industry is rapidly globalizing"
    )

    pre_context = build_preresearch_context(test_input.lead_name, test_input.company)
    print("Preresearch_context:", pre_context.model_dump_json(indent=2, ensure_ascii=False))

    # this should be a cheap, instant cache hit — we already researched this
    # exact lead/company pair earlier in the project
    research_findings = get_research_findings(test_input.lead_name, test_input.company)
    print("Research findings:", research_findings.model_dump_json(indent=2, ensure_ascii=False))

    result = merge_all_research(test_input, pre_context, research_findings)
    print("Merge_all_research results:", result.model_dump_json(indent=2, ensure_ascii=False))


