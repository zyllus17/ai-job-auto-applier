#!/usr/bin/env python3
"""Application funnel analytics and LinkedIn profile optimizer."""

import csv
from pathlib import Path
from typing import Dict, Any, List
from collections import Counter

REPO_ROOT = Path(__file__).parent.parent.resolve()
TRACKER_CSV = REPO_ROOT / "job_search_tracker.csv"
if not TRACKER_CSV.exists() and (REPO_ROOT / "scratch" / "job_tracker.csv").exists():
    TRACKER_CSV = REPO_ROOT / "scratch" / "job_tracker.csv"

class FunnelTracker:
    """Tracks: Discovered -> Staged -> Applied -> Interview -> Offer"""
    
    def __init__(self, tracker_file = TRACKER_CSV):
        self.tracker_file = Path(tracker_file)
        self._ensure_file()
        
    def _ensure_file(self):
        self.tracker_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.tracker_file.exists():
            with open(self.tracker_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'company', 'title', 'fitScore', 'status', 'missingSkill', 'suggestedProject', 'location', 'url', 'notes'])

    def update_status(self, job_id_or_company: str, new_status: str, role: str = '', skills: str = ''):
        """Update a job's status in the tracker CSV."""
        rows = []
        updated = False
        
        with open(self.tracker_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or ['timestamp', 'company', 'title', 'fitScore', 'status', 'missingSkill', 'suggestedProject', 'location', 'url', 'notes']
            for row in reader:
                target = row.get('company', '') or row.get('job_id', '')
                if job_id_or_company.lower() in target.lower():
                    row['status'] = new_status
                    if role and 'title' in row: row['title'] = role
                    if skills and 'missingSkill' in row: row['missingSkill'] = skills
                    updated = True
                rows.append(row)
                
        if not updated:
            rows.append({
                'company': job_id_or_company,
                'status': new_status,
                'title': role,
                'missingSkill': skills
            })
            
        with open(self.tracker_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)

    def generate_report(self) -> str:
        """Generate a formatted analytics report."""
        if not self.tracker_file.exists():
            return "No data available."
            
        statuses = []
        skills_counter = Counter()
        companies = set()
        
        with open(self.tracker_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                st = row.get('status', 'Discovered').strip()
                statuses.append(st)
                comp = row.get('company', '').strip()
                if comp: companies.add(comp)
                
                # Check skills from missingSkill or skills_requested
                skill_val = row.get('missingSkill') or row.get('skills_requested') or ''
                if skill_val and skill_val.lower() not in ['none', 'n/a', '-']:
                    # Extract clean skill name (e.g. "LangGraph / Multi-Agent" -> "LangGraph")
                    clean_skill = skill_val.split('(')[0].strip()
                    for s in clean_skill.split('/'):
                        s_clean = s.strip()
                        if len(s_clean) > 2:
                            skills_counter.update([s_clean])
                    
        status_counts = Counter(statuses)
        total = sum(status_counts.values())
        
        report = []
        report.append("📊 **Job Funnel Analytics Report**\n")
        report.append(f"**Total Tracked Opportunities:** {total} across {len(companies)} companies\n")
        
        report.append("## 📈 Application Funnel Stages")
        for status_label, count in status_counts.most_common():
            report.append(f"- **{status_label}:** {count}")
            
        report.append("\n## 🔥 Top High-Demand Skill Gaps Across Postings")
        for skill, count in skills_counter.most_common(6):
            report.append(f"- **{skill}:** requested in {count} postings")
            
        return "\n".join(report)


class LinkedInOptimizer:
    """Generates LinkedIn profile improvement suggestions."""
    
    def analyze_job_trends(self, tracker_file: Path = TRACKER_CSV) -> Dict[str, Any]:
        """Analyze all evaluated jobs."""
        skills_counter = Counter()
        roles_counter = Counter()
        
        if tracker_file.exists():
            with open(tracker_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    title = row.get('title') or row.get('role') or ''
                    if title:
                        roles_counter.update([title.strip()])
                    skill_val = row.get('missingSkill') or row.get('skills_requested') or ''
                    if skill_val and skill_val.lower() not in ['none', 'n/a', '-']:
                        clean_skill = skill_val.split('(')[0].strip()
                        for s in clean_skill.split('/'):
                            s_clean = s.strip()
                            if len(s_clean) > 2:
                                skills_counter.update([s_clean])
                        
        return {
            "top_skills": [skill for skill, _ in skills_counter.most_common(10)],
            "top_roles": [role for role, _ in roles_counter.most_common(5)]
        }
    
    def suggest_profile_updates(self, current_profile: dict, trends: dict) -> str:
        """Generate specific suggestions."""
        top_skills = ", ".join(trends.get("top_skills", []))
        top_roles = ", ".join(trends.get("top_roles", []))
        
        report = []
        report.append("# LinkedIn Profile Optimization Suggestions\n")
        
        report.append("## Headline Update")
        report.append(f"Consider updating headline to target: **{top_roles}**")
        
        report.append("\n## About Section")
        report.append(f"Ensure these highly demanded skills are mentioned: **{top_skills}**")
        
        report.append("\n## Skills Section")
        report.append("Endorse and pin these top skills to your profile.")
        
        report.append("\n## Featured Projects")
        report.append("Pin recent projects matching these skills to visually demonstrate competence.")
        
        return "\n".join(report)

if __name__ == "__main__":
    tracker = FunnelTracker()
    print(tracker.generate_report())
