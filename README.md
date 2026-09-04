# LEAv2 — Lead Engagement Agent
LEA v2 is an AI-assisted lead research and outreach system designed for personalized B2B sales in Japan. It transforms fragmented company and contact information into evidence-based outreach by identifying buying signals, selecting an appropriate message angle, and generating culturally sensitive Japanese or English messages.

Sales outreach usually requires several disconnected steps: researching a company, identifying relevant buying signals, understanding the contact’s role, deciding on the right message angle, and writing culturally appropriate outreach. Doing this manually is slow, while fully automated approaches often produce generic, overly assertive, or poorly supported messages. LEAv2 shortens all these steps

Built for Language instruction company (that has mercari, line, NEC as its clients) as part of an internal, multi-agent sales tooling project. 

**Live demo:** https://lead-engagement-agent-v2.streamlit.app
![LEAv2 demo](demo.gif)

## What it does

Give it a company, whatever you already know about a contact there, and any personalization angles you have — a warm introduction, a known mutual connection, a buying signal you noticed, something relevant about their role or industry. LEAv2 fills in the rest:

- Checks a private CSV of known connections and past competitor client lists for any existing angle in
- Runs a  research agent to understand the target company, a strategy agent to evaluate available messaging angles, and a writing agent to draft the messages
- Generates a structured **Engagement Plan**: primary and backup contacts(email/phone/linkedin), a recommended call-to-action, likely objections to prepare for, and a chosen personalization angle
- Drafts two outreach messages one in Japanese, then adapts each into English

## How it's built

- **Python** + **Streamlit** for the UI
- **Claude API** (Anthropic) — one model call for research (with a live web-search tool), one for strategy generation, one per message for writing, and a smaller model for trimming over-length drafts
- **Pydantic** — every model output (research findings, the engagement plan, the written messages) is validated against a strict schema, so nothing malformed ever reaches the UI
- Local JSON-file caching at two levels (research findings, and full engagement plans) to avoid re-paying for identical work
- A CSV-backed lookup of known personal connections and competitor client lists, used before any AI research runs


## Status

This is **V1** — the current scope stops at producing a contact-ready Engagement Plan and two draft messages. Planned future versions will handle choosing the outreach angle more adaptively (V2) and managing send timing, sequencing, and follow-up (V3).

