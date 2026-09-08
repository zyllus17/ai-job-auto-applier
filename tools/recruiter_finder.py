#!/usr/bin/env python3
"""Recruiter finder using Google X-Ray search (no LinkedIn login needed)."""

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

def google_xray_search(company: str, role_keywords: list[str]) -> list[dict]:
    """Search Google for LinkedIn profiles matching company + role.
    
    Constructs queries like:
    site:linkedin.com/in/ "Stellantis" ("Engineering Manager" OR "Technical Recruiter")
    
    Returns: [{name, linkedin_url, title, company}]
    """
    candidate_profile = Path(__file__).parent / "candidate_profile.json"
    if not candidate_profile.exists():
        candidate_profile = Path(__file__).parent.parent / "candidate_profile.json"
    current_company = ""
    if candidate_profile.exists():
        try:
            with open(candidate_profile, 'r', encoding='utf-8') as f:
                profile = json.load(f)
                current_company = profile.get("current_company", "").lower()
        except Exception:
            pass
            
    if current_company and current_company in company.lower():
        # User's current company must NEVER appear in results
        print(f"[SKIP] Company '{company}' matches current employer '{current_company}'. Skipping outreach discovery.")
        return []
        
    roles = " OR ".join(f'"{r}"' for r in role_keywords)
    query = f'site:linkedin.com/in/ "{company}" ({roles})'
    search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
    ddg_url = f"https://duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
    
    # Try passive DuckDuckGo HTML lookup
    results = []
    try:
        req = urllib.request.Request(
            ddg_url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            # Extract linkedin profile links: linkedin.com/in/[slug]
            matches = re.findall(r'https?://[a-z\.]*linkedin\.com/in/([a-zA-Z0-9_\-]+)', html)
            for slug in set(matches[:5]):
                name = slug.replace('-', ' ').title()
                results.append({
                    "name": name,
                    "linkedin_url": f"https://www.linkedin.com/in/{slug}",
                    "title": role_keywords[0] if role_keywords else "Hiring Manager",
                    "company": company,
                    "search_query": query
                })
    except Exception:
        pass

    if not results:
        results.append({
            "name": "Hiring Team Lead",
            "linkedin_url": search_url,
            "title": role_keywords[0] if role_keywords else "Recruiter",
            "company": company,
            "search_query": query,
            "notes": "Direct Google X-Ray query generated"
        })
    return results

def generate_email_permutations(first: str, last: str, domain: str) -> list[str]:
    """Generate common corporate email format guesses.
    Returns: ['john.doe@company.com', 'jdoe@company.com', ...]
    """
    f = first.lower().replace(' ', '')
    l = last.lower().replace(' ', '')
    return [
        f"{f}.{l}@{domain}",
        f"{f}{l}@{domain}",
        f"{f}@{domain}",
        f"{f[0]}{l}@{domain}",
        f"{f}_{l}@{domain}",
        f"{f[0]}.{l}@{domain}"
    ]

def find_company_domain(company_name: str) -> str:
    """Best-effort company domain lookup."""
    clean_name = urllib.parse.quote_plus(company_name.lower().replace(' ', '').replace(',', '').replace('.', ''))
    return f"{clean_name}.com"

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Find recruiters or hiring managers for a company via Google X-Ray")
    parser.add_argument("--company", required=True, help="Target company name")
    parser.add_argument("--roles", nargs="+", default=["Engineering Manager", "Technical Recruiter", "Talent Acquisition"], help="Target role keywords")
    args = parser.parse_args()
    
    findings = google_xray_search(args.company, args.roles)
    domain = find_company_domain(args.company)
    print(f"\n🔍 Recruiter Search Results for '{args.company}' (Domain: {domain}):")
    for f in findings:
        print(f"- Name: {f['name']}")
        print(f"  Role: {f['title']}")
        print(f"  LinkedIn: {f['linkedin_url']}")
        first = f['name'].split()[0]
        last = f['name'].split()[-1] if len(f['name'].split()) > 1 else 'doe'
        emails = generate_email_permutations(first, last, domain)[:3]
        print(f"  Guessed Emails: {', '.join(emails)}\n")
