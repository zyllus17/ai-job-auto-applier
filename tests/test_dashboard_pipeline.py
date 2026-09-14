"""Tests for Dashboard Candidate Pipeline & Status Management.

Validates:
1. Stable row indexing (_orig_idx) across filtering, search, and sorting in /api/jobs.
2. Status updates via URL matching, (company, title) matching, and index fallback.
3. 'Closed' status integration in CSV persistence, /api/stats, and /api/analytics funnel.
4. Auto-apply endpoint action contract.
"""

import os
import csv
import tempfile
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from dashboard.server import (
    app,
    read_tracker_csv,
    get_jobs,
    get_stats,
    get_analytics,
    update_job_status,
    JobStatusUpdate,
    ApplyJobInput,
)

SAMPLE_TRACKER_DATA = [
    {
        "timestamp": "2026-09-08 00:23:00",
        "company": "Alpha Dynamics",
        "title": "Senior AI Automation Engineer",
        "fitScore": "95",
        "status": "Staged - Ready to Submit",
        "missingSkill": "LangGraph",
        "suggestedProject": "FastRAG-Agent",
        "location": "Remote",
        "url": "https://jobs.lever.co/alpha/111",
        "notes": "Top fit"
    },
    {
        "timestamp": "2026-09-08 00:24:00",
        "company": "Beta Cloud",
        "title": "LLM Solutions Architect",
        "fitScore": "88",
        "status": "Applied",
        "missingSkill": "Vector DB",
        "suggestedProject": "Semantic Search",
        "location": "Bengaluru",
        "url": "https://jobs.ashbyhq.com/beta/222",
        "notes": "Applied via ATS"
    },
    {
        "timestamp": "2026-09-08 00:25:00",
        "company": "Gamma AI",
        "title": "Machine Learning Engineer",
        "fitScore": "72",
        "status": "Interview",
        "missingSkill": "PyTorch",
        "suggestedProject": "Vision Classifier",
        "location": "Remote",
        "url": "https://boards.greenhouse.io/gamma/333",
        "notes": "Round 1 scheduled"
    },
    {
        "timestamp": "2026-09-08 00:26:00",
        "company": "Delta Systems",
        "title": "Full Stack AI Engineer",
        "fitScore": "65",
        "status": "Closed",
        "missingSkill": "React",
        "suggestedProject": "Frontend UI",
        "location": "London",
        "url": "https://workday.com/delta/444",
        "notes": "Position expired"
    }
]


@pytest.fixture
def mock_tracker_csv(tmp_path, monkeypatch):
    """Creates a temporary tracker CSV and monkeypatches TRACKER_CSV in dashboard.server."""
    csv_file = tmp_path / "test_job_search_tracker.csv"
    fieldnames = [
        "timestamp", "company", "title", "fitScore", "status",
        "missingSkill", "suggestedProject", "location", "url", "notes"
    ]
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(SAMPLE_TRACKER_DATA)

    monkeypatch.setattr("dashboard.server.TRACKER_CSV", csv_file)
    return csv_file


@pytest.mark.asyncio
async def test_stable_row_indices_with_search_and_sort(mock_tracker_csv):
    """Verify that idx reflects the original CSV row index (_orig_idx) regardless of search or sorting."""
    # 1. Unfiltered
    res_all = await get_jobs(search="", page=1, per_page=10)
    jobs_all = res_all['data']
    assert len(jobs_all) == 4
    assert jobs_all[0]['idx'] == 0
    assert jobs_all[1]['idx'] == 1
    assert jobs_all[2]['idx'] == 2
    assert jobs_all[3]['idx'] == 3

    # 2. Filtered by search (only Beta Cloud matching)
    res_search = await get_jobs(search="Beta", page=1, per_page=10)
    jobs_search = res_search['data']
    assert len(jobs_search) == 1
    assert jobs_search[0]['company'] == "Beta Cloud"
    # MUST retain original CSV index 1, not 0!
    assert jobs_search[0]['idx'] == 1

    # 3. Sorted by company descending (Gamma -> Delta -> Beta -> Alpha)
    res_sort = await get_jobs(sort_by="company", sort_order="desc", page=1, per_page=10)
    jobs_sort = res_sort['data']
    assert jobs_sort[0]['company'] == "Gamma AI"
    assert jobs_sort[0]['idx'] == 2  # Gamma was row 2 in original CSV
    assert jobs_sort[1]['company'] == "Delta Systems"
    assert jobs_sort[1]['idx'] == 3  # Delta was row 3 in original CSV


@pytest.mark.asyncio
async def test_update_status_by_url_and_orig_idx(mock_tracker_csv):
    """Test updating job status via URL, confirming persistence in CSV and broadcast."""
    with patch("dashboard.server.manager.broadcast", new_callable=AsyncMock) as mock_broadcast:
        # Update Beta Cloud (idx 1) by URL to "Closed"
        update_data = JobStatusUpdate(
            status="Closed",
            url="https://jobs.ashbyhq.com/beta/222",
            company="Beta Cloud",
            title="LLM Solutions Architect"
        )
        res = await update_job_status(idx=999, data=update_data)  # intentionally bogus idx
        assert res['status'] == "success"
        assert res['new_status'] == "Closed"
        assert res['idx'] == 1

        mock_broadcast.assert_called_once()
        b_arg = mock_broadcast.call_args[0][0]
        assert b_arg['type'] == 'job_updated'
        assert b_arg['idx'] == 1
        assert b_arg['status'] == 'Closed'

    # Verify CSV persistence
    rows = read_tracker_csv()
    assert rows[1]['company'] == "Beta Cloud"
    assert rows[1]['status'] == "Closed"


@pytest.mark.asyncio
async def test_update_status_by_idx_fallback(mock_tracker_csv):
    """Test status update fallback when URL is not provided."""
    with patch("dashboard.server.manager.broadcast", new_callable=AsyncMock):
        update_data = JobStatusUpdate(status="Offer")
        res = await update_job_status(idx=0, data=update_data)
        assert res['status'] == "success"
        assert res['new_status'] == "Offer"
        assert res['idx'] == 0

    rows = read_tracker_csv()
    assert rows[0]['company'] == "Alpha Dynamics"
    assert rows[0]['status'] == "Offer"


@pytest.mark.asyncio
async def test_stats_and_analytics_include_closed_count(mock_tracker_csv):
    """Test that /api/stats and /api/analytics properly count and return closed status."""
    stats = await get_stats()
    assert stats['total_jobs'] == 4
    assert stats['staged'] == 1
    assert stats['applied'] == 1
    assert stats['interviews'] == 1
    assert stats['closed'] == 1  # Delta Systems is Closed

    analytics = await get_analytics()
    funnel = analytics['funnel']
    assert funnel['discovered'] == 4
    assert funnel['staged'] == 1
    assert funnel['applied'] == 1
    assert funnel['interview'] == 1
    assert funnel['closed'] == 1


@pytest.mark.asyncio
async def test_api_apply_job_input_contract():
    """Verify ApplyJobInput schema and validation."""
    data = ApplyJobInput(url="https://jobs.lever.co/test/123", mode="semi-auto")
    assert data.url == "https://jobs.lever.co/test/123"
    assert data.mode == "semi-auto"

    data_default = ApplyJobInput(url="https://jobs.ashbyhq.com/test/456")
    assert data_default.mode == "semi-auto"
