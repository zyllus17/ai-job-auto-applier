# Search Queries for Job Scraper - Maruf Hassan

## Installed portal CLIs (primary for `/scrape`)
`/scrape` discovers every portal skill under `.agents/skills/*/SKILL.md` and runs its CLI first:
- `linkedin-search` - Global LinkedIn job listings
- `freehire-search` - FreeHire remote developer jobs

The `site:` query templates below are the **WebSearch fallback** and broad discovery net.

## Target Search Sites
- **linkedin.com/jobs** - Primary global network
- **remoteok.com / wellfound.com** - Global remote startup roles
- **freehire.com** - Remote contractor/fulltime engineering
- **indeed.com / naukri.com** - India & Remote technology listings

## Query Categories

### Priority 1: AI Automation & LLM Engineering (Strongest Growth Direction)
Matches Floor Boss experience: Gemini LLM integration, agentic workflows, API orchestration, and Slack bots.
```
site:linkedin.com/jobs "AI Automation Engineer" remote
site:linkedin.com/jobs "LLM Engineer" remote
site:linkedin.com/jobs "Generative AI Engineer" "Python" remote
site:linkedin.com/jobs "AI Engineer" ("Gemini" OR "OpenAI" OR "Agentic") remote
"AI Automation Engineer" (remote OR "India")
"LLM Integration Engineer" remote
```

### Priority 2: Senior Flutter & Mobile Engineering (Deep 5+ YOE Core)
Matches ELSA Speak, SuperBrains, Nyburs, and QuestHopp track record.
```
site:linkedin.com/jobs "Senior Flutter Developer" remote
site:linkedin.com/jobs "Lead Flutter Developer" (remote OR "India")
site:linkedin.com/jobs "Flutter Engineer" "Riverpod" remote
site:wellfound.com/jobs "Senior Flutter Developer"
site:remoteok.com "Flutter"
```

### Priority 3: Mobile AI & Cross-Platform AI Developer (Unique Intersection)
Combining Flutter mobile frontend scale with on-device / backend LLM capabilities.
```
site:linkedin.com/jobs "Mobile AI Engineer" remote
site:linkedin.com/jobs "Flutter" ("AI" OR "LLM") developer remote
"Cross-platform developer" "Generative AI" remote
```

### Priority 4: Full-Stack / Workflow Automation & API Integrations
```
site:linkedin.com/jobs "Workflow Automation Engineer" remote
site:linkedin.com/jobs "API Integration Engineer" "Python" remote
```

## Location & Remote Filter
- **Tier 1 (Preferred):** Remote Worldwide (US, EU, UK, APAC, Global)
- **Tier 2:** Remote India
- **Tier 3:** Hybrid / Onsite in Kolkata, India
- **Tier 4:** Open to Relocation (Europe, US, Middle East, APAC)

## Language Filter
- English (Working language)
- Hindi & Bengali (Native)

## Date Filter
Only include jobs posted within the last 14 days, or with active deadlines.

