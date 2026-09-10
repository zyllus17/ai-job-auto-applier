#!/usr/bin/env python3
"""Generates personalized outreach messages."""

import random
from pathlib import Path

def draft_outreach(recruiter_name: str, company: str, role_title: str, candidate_achievement: str, candidate_linkedin: str) -> dict:
    """Returns {'email': str, 'linkedin_request': str}"""
    
    linkedin_opts = [
        f"Hey {recruiter_name}, I saw you posted a {role_title} role at {company}. I have worked on similar technology and stuff, if you got a min, please check my Linkedin Profile to check the cool stuff I have built!",
        f"Hi {recruiter_name}! I saw you posted a {role_title} listing. I have worked on similar technology and stuff, if you got a min, please check my Linkedin Profile to check the cool stuff I have built!"
    ]
    linkedin_request = random.choice(linkedin_opts)
    
    email = (f"Hi {recruiter_name},\n\n"
             f"I noticed the {role_title} opening at {company} and wanted to reach out directly. "
             f"My background aligns closely with the technical requirements, particularly when I {candidate_achievement}. "
             f"I've attached my resume for your review and would love to chat if you think there might be a fit. "
             f"Thanks for your time!\n\nBest,\n[Your Name]\n{candidate_linkedin}")
             
    import re
    repo_root = Path(__file__).parent.parent.resolve()
    safe_c = re.sub(r'[^a-zA-Z0-9_\-]+', '_', company.strip()).strip('_')
    safe_t = re.sub(r'[^a-zA-Z0-9_\-]+', '_', role_title.strip()).strip('_')
    out_dir = repo_root / "documents" / "applications" / f"{safe_c}_{safe_t}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "outreach.md"
    
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(f"# Outreach Drafts for {role_title} at {company}\n\n")
        f.write(f"## LinkedIn Connection Request\n```text\n{linkedin_request}\n```\n\n")
        f.write(f"## Cold Email\n```text\n{email}\n```\n")
        
    return {'email': email, 'linkedin_request': linkedin_request}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate cold outreach draft (Email + LinkedIn connection request)")
    parser.add_argument("--recruiter", default="Hiring Manager", help="Recruiter name")
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument("--role", required=True, help="Job title")
    parser.add_argument("--achievement", default="architected high-throughput Gemini AI Slack agents cutting reporting time by 70%", help="Highlight achievement")
    parser.add_argument("--linkedin", default="https://linkedin.com/in/maruf-hassan", help="Candidate LinkedIn URL")
    args = parser.parse_args()
    
    draft = draft_outreach(args.recruiter, args.company, args.role, args.achievement, args.linkedin)
    print("\n[OK] Draft generated successfully in documents/applications/:\n")
    print("--- LinkedIn Connection Request ---")
    print(draft['linkedin_request'])
    print("\n--- Cold Email ---")
    print(draft['email'])
