# research_agent.py flow
# Schema — Finding + ResearchFindings (moved to models.py)
# Input — company (required), lead_name (optional, from LEAInput).
# System prompt — define role, max_uses cap, "skip person search if no name," instruct to call record_findings when done.
# Tools — web_search (real) + record_findings (custom schema tool).
# Call — tools=[web_search, record_findings], tool_choice left default ("auto").
# Parse — loop response.content, grab the block where type == "tool_use" and name == "record_findings", validate .input into ResearchFindings.
# Failure case — Claude never calls record_findings (exhausts turns just searching). Flag for later, not solving now.
# Test — run against Mercari from sample_input.json.


from models import ContactDetails, Finding, ResearchFindings
from dotenv import load_dotenv
from anthropic import Anthropic
from cache import save_research_to_cache
from loggers import log_api_cost, log_search_query

MAX_SEARCHES = 7

SYSTEM_PROMPT = f"""You are a research assistant preparing a salesperson for outreach to a specific lead at a specific company.

You have a web search tool with a maximum of {MAX_SEARCHES} searches. Spend them deliberately — do not stop after the first search that returns something useful. Research from multiple distinct angles before finishing.

If a lead name is provided, person-level research is the first priority. However, company-level evidence should still be collected when it explains why this person may care now.

Your job:
1. If a lead name is provided, research that specific person first — their
role, responsibilities, background, and public professional presence.
Prioritize concrete, current material a salesperson could reference
directly in conversation over generic career history: a recent interview,
an article or op-ed they appear in, a stated professional philosophy or
ideology, a book or publication they've authored, or anything else that
hints at what they're responsible for, struggling with, or care about in
their role. Run one search using "site:linkedin.com" plus their name to
try to find their LinkedIn profile. If LinkedIn is not accessible or the
result is low-quality, do not keep searching LinkedIn repeatedly — move on
to other angles. Summarize their career background/current role in at most
one sentence, and spend the majority of your findings on the specific,
on-the-ground material described above. Return only the 3 most relevant
person-level findings, prioritizing recency and specificity over quantity.
2. Optionally, if you find signs that this person has an active, professionally relevant presence 
on X (formerly Twitter) — not just a stray mention — you may run one additional search such as 
"site:x.com" plus their name to check. Only do this if it seems genuinely likely to surface something 
meaningful; do not run it as a default step for every lead.
3. Research the company to collect evidence that explains why this person may care now — recent news,
 hiring activity, or the company's own website (careers page, about page, public deck). Do not default to 
 generic headline signals like "international expansion" just because they're easy to find — a signal is 
 only worth including if it's genuinely tied to this specific person's day-to-day responsibilities, not 
 simply the loudest news about the company.
4. If no lead name is provided, skip person-specific searches entirely and focus only on company-level 
research.
5. Backup contacts are usually only worth noting opportunistically — if you come across someone plausibly 
relevant while researching the primary lead, record them. However, if your research on the named lead is
 turning up limited public information, deliberately spend some of your remaining searches on the people 
 around them instead — their team, colleagues, direct reports, or reporting structure — both as additional 
 context useful for personalization, and as stronger candidates for backup contacts. Prefer people at or near
  the same level as the primary lead — peers, team members, direct reports, or others in 
  HR/L&D/Talent/department-level roles — over top executives like a CEO or President: a senior executive is 
  often harder to reach via cold outreach, not an easier fallback, so only record one as a last resort if 
  nothing more peer-level turns up. Also prefer someone whose role is scoped to the lead's own market or 
  region (e.g., Japan, APAC) over someone in a matching department but at a global/HQ level — a global-scoped 
  contact may have limited visibility or authority over decisions specific to that market, so record one only
   if no locally- or regionally-scoped equivalent turns up. Only record backup contacts whose role is relevant
   — HR, L&D, Talent, Global HR, corporate planning, global business, someone leading engineers, an executive
    (last resort only), or another department-level contact route — not random employees mentioned in passing.
     When looking for these peer-level candidates, use search patterns more likely to return a page that 
     actually lists names and titles — such as the company's "leadership team," "management team," or 
     organization chart — rather than general news or hiring searches, which often don't name specific 
     individuals at all.
6. 6. Search craft: when the lead or company is based in Japan, use a mixed-language approach rather than 
defaulting to one language for everything. Favor Japanese phrasing for company pages, organization/leadership
 listings, and personnel-announcement searches — these often use specific terms like 就任 or 人事異動 and are frequently Japanese-only. Keep LinkedIn searches and searches for official global press releases (from an international parent company) in English, since these are commonly maintained in English even for Japan-based individuals and companies. Keep each individual query short and focused, roughly 3-6 words, rather than combining many qualifiers into one search — overly specific queries often return fewer useful results, not more. If a search returns nothing useful, don't retry with a slightly reworded version of the same query — pivot to a genuinely different angle instead, such as a different language, a different site, or a different term.
7. If a search ever returns a max_uses_exceeded error, that means your entire search budget has been used up. Do not attempt another web_search call under any circumstances, even if research feels incomplete. Immediately call raw_research with whatever findings you have gathered so far. Retrying will not produce a different result — it will only return the same error again and waste effort.

Each finding should be specific enough to use directly in a personalized message — avoid vague generalities. 
Whenever you record a finding, include the source URL if you have one.

Once you have finished researching, call the raw_research tool with everything you found. 
Do not call it before you are done searching."""

tools = [
    {"type": "web_search_20250305", "name": "web_search", "max_uses": MAX_SEARCHES},
    #this is a custom tool, which is a schema, so that claudes' response gets forced into the JSON shape stated in it
    #there's no "tool choice" argument so tool_choice is default set to auto. which means claude is free to reply in 
    # plain english if it wants to. 
    {
        "name": "raw_research",
        "description": "Record the structured research findings once research is complete.",
        "input_schema": ResearchFindings.model_json_schema()
    }
]

load_dotenv()
client = Anthropic()

def run_research(lead_name, company, run_id=None):

    response = client.messages.create(
        model = "claude-sonnet-5",
        max_tokens = 2048,
                system = [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        tools = tools,
        tool_choice = {"type":"any"},
        messages = [
            {
                "role" : "user",
                "content" : f"Lead: {lead_name}\n company: {company}" 
            }
        ]
    )

    lead_id = f"{company} | {lead_name or 'unknown'}"

    #=============== DEBUG: visibility step delete when done building==================
    print(f"stop_reason: {response.stop_reason}")
    print(f"usage: {response.usage}")

    for i, block in enumerate(response.content):
        # server_tool_use is the block type claude uses to run a real web search instead of tool_use 
        # which is the block type for raw_research
        if block.type == "server_tool_use":
            query = block.input.get('query')
            print(f"{i}: SEARCH -> {query}")
            log_search_query(run_id, lead_id, query)
        else:
            print(f"{i}: {block.type}")
    #==============================================================================================

    web_searches_used = sum(1 for block in response.content if block.type == "server_tool_use")
    log_api_cost(
        run_id=run_id,
        lead_id=lead_id,
        call_type="run_research",
        model="claude-sonnet-5",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        web_searches=web_searches_used,
        cache_creation_input_tokens=getattr(response.usage, "cache_creation_input_tokens", 0),
        cache_read_input_tokens=getattr(response.usage, "cache_read_input_tokens", 0)
    )

    #PARSING STEP (2 parts)
    for block in response.content:
        if block.type == "tool_use" and block.name == "raw_research":
            findings = ResearchFindings(**block.input)
            save_research_to_cache(company, [lead_name], findings)
            return findings

if __name__ == "__main__":
    findings = run_research("Masayuki Igarashi", "Leica Microsystems")
    print(findings.model_dump_json(indent=2,ensure_ascii=False))

