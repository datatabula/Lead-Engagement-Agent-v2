from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from pprint import pprint

class BuyingSignalData(BaseModel):
    company_name: str
    industry: Optional[str] = None
    icp_score: Optional[int] = None
    intent_score: Optional[int] = None
    final_qualification_score: Optional[int] = None
    signal_category: Optional[str] = None
    signal: Optional[str] = None
    signal_summary: Optional[str] = None
    matched_keywords: List[str] = []
    publication_date: Optional[str] = None
    freshness_days: Optional[int] = None

    #subset of json export from LEAv1
class ContactDetails(BaseModel):
    name: Optional[str] = None
    name_romanized: Optional[str] = None
    role_title: Optional[str] = None
    department: Optional[str] = None
    contact_url_or_email: Optional[str] = None
    email: Optional[str] = None
    email_source: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    source_url: Optional[str] = None

class FoundContact(BaseModel):
    company_name_japanese: Optional[str] = None
    company_name_english: Optional[str] = None
    official_website: Optional[str] = None
    primary_contact: Optional[ContactDetails] = None
    backup_contacts: List[ContactDetails] = []
    raw_candidate: Optional[ContactDetails] = None

class LEAInput(BaseModel):
    found_contact: Optional[str] = None
    found_buying_signal: Optional[str] = None
    lead_name: Optional[str] = None
    company: str
    engagement_type: Literal["warm", "distant_connection", "2nd_touch_no_connection", "1st_touch_no_connection"] = "1st_touch_no_connection"
    warm: Optional[str] = None
    rapport_position: Optional[str] = None
    rapport_company: Optional[str] = None
    rapport_industry: Optional[str] = None
    likely_objection: List[str] = []
    buying_signals: List[str] = []
    i_am: Literal["marc", "john", "kasumi", "yoshie"] = "marc"
    method: Literal["email", "linkedin"] = "linkedin"
    calendly: bool = False
    more_context: Optional[str] = None

class Finding(BaseModel):
    content: str
    evidence_url: Optional[str]= None

class ResearchFindings(BaseModel):
    person_lvl_findings: List[Finding] = []
    company_lvl_findings: List[Finding] = []
    backup_contacts: List[ContactDetails] = []

class DistantConnection(BaseModel):
    whose_connection: str
    contact: ContactDetails

class PreResearchContext(BaseModel):
    has_distant_cxn: List[DistantConnection] = []
    competitor_it_was_found_under: Optional[str] = None
    needs_hr_fallback: bool = False
    has_cached_research: Optional[ResearchFindings] = None

class PersonalizationLevel(BaseModel):
    availability: bool = False
    content: Optional[str] = None
    evidence_url: Optional[str] = None

#"warm must hold a PersonalizationLevel object. it would be built with a fresh instance of PersonalizationLevel(), So that means it's contain {availability, content, and evidence_url}"
class PersonalizationHierarchy(BaseModel):
    warm: PersonalizationLevel = PersonalizationLevel()
    distant_connection: PersonalizationLevel = PersonalizationLevel()
    agents_research: PersonalizationLevel = PersonalizationLevel()
    buying_signal: PersonalizationLevel = PersonalizationLevel()
    position_rapport: PersonalizationLevel = PersonalizationLevel()
    company_rapport: PersonalizationLevel = PersonalizationLevel()
    industry_rapport: PersonalizationLevel = PersonalizationLevel()

class LikelyObjection(BaseModel):
    objection: str
    reason: str


class Signal(BaseModel):
    name: str
    evidence_url: Optional[str] = None


class MessageStrategy(BaseModel):
    chosen_personalization_level: Literal[
        "warm", "distant_connection", "agents_research", "buying_signal",
        "position_rapport", "company_rapport", "industry_rapport"
    ]
    matched_rapport_category: Optional[Literal[
        "HR / L&D / Talent Development", "HR Business Partner / Global HR / Global Mobility",
        "Engineering Manager", "Engineer / Software Engineer",
        "Tech Lead / Team Lead / Project Manager / Product Manager",
        "Department Head / General Manager", "Sales Manager / Account Manager",
        "Customer Success", "Operations Manager", "Senior Manager / Executive",
        "Global Expansion", "Overseas Offices / Sites", "International Workforce",
        "Foreign Employee Hiring", "Global Engineering / Development",
        "International Customers", "Cross-Border Projects", "M&A / Integration",
        "Rapid Growth", "New Overseas Market Entry", "Global Leadership Initiative",
        "Internal Language Training", "English as a Common Business Language",
        "Global Meetings / Collaboration", "Global Customer Support / Service",
        "International Partnerships", "Global Transformation / Reorganization",
        "Strong Overseas Revenue / International Business",
        "Manufacturing", "Automotive", "Banking", "Consulting", "Pharmaceutical",
        "IT / SaaS", "Electronics", "Trading Companies", "Logistics", "Retail",
        "Hospitality", "HR / L&D"
    ]] = None
    rapport_content: Optional[str] = None
    objection_to_address: Optional[str] = None
    include_auth_signal: bool = False


class EngagementPlan(BaseModel):
    company_name_jp: Optional[str] = None
    company_name_en: str
    industry: Optional[str] = None

    primary_contact: Optional[ContactDetails] = None
    backup_contacts: List[ContactDetails] = []
    general_inquiry_url: Optional[str] = None

    signals_found: List[Signal] = []

    engagement_type: Literal["warm", "distant_connection", "2nd_touch_no_connection", "1st_touch_no_connection"]

    personalization: PersonalizationHierarchy

    likely_objections: List[LikelyObjection] = []

    cta: Literal["forward_me", "meeting"]

    contact_role_category: Literal[
        "CEO, founder, country manager",
        "HR, HRBP, L&D, talent development",
        "Engineering or technology leader",
        "Team lead, project manager, product manager",
        "Procurement or administration",
        "Sales or account manager",
        "Recruiter or talent acquisition",
        "Unknown role or uncertain owner",
    ]
    seniority_tier: Literal["senior", "mid_senior", "non_senior"]
    recommended_contact_time: Optional[str] = None
    other_recommended_next_actions: Optional[str] = None

    message_strategies: List[MessageStrategy] = Field(min_length=2, max_length=2)

class WrittenMessage(BaseModel):
    japanese: str
    english: str
    subject_jp: Optional[str] = None
    subject_en: Optional[str] = None

class WritingOutput(BaseModel):
    messages: List[WrittenMessage] = Field(min_length=2, max_length=2)

class LEAv2Output(BaseModel):
    engagement_plan: EngagementPlan
    messages: List[WrittenMessage] = Field(min_length=2, max_length=2)
    research_findings: Optional[ResearchFindings] = None

if __name__ == "__main__":

    # test 1: LikelyObjection
    test_objection = LikelyObjection(
        objection="already have a provider",
        reason="appeared on a competitor's client list"
    )

    # test 2: Signal
    test_signal = Signal(
        name="hiring international talent",
        evidence_url="https://example.com/job-posting"
    )

    # test 3: MessageStrategy
    test_strategy = MessageStrategy(
        chosen_personalization_level="position_rapport",
        rapport_content="HR leaders often mention struggling with real meeting communication",
        objection_to_address=None,
        include_auth_signal=True
    )

    # test 4: EngagementPlan — reuses the objects built above, plus a second
    # MessageStrategy, to build one complete, realistic plan
    test_plan = EngagementPlan(
        company_name_en="Test Company",
        engagement_type="1st_touch_no_connection",
        personalization=PersonalizationHierarchy(),
        cta="meeting",
        likely_objections=[test_objection],
        signals_found=[test_signal],
        message_strategies=[
            test_strategy,
            MessageStrategy(chosen_personalization_level="industry_rapport")
        ]
    )
    pprint(test_plan.model_dump(), sort_dicts=False)

