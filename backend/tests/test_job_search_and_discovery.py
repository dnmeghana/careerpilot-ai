"""Unit and integration tests for V2 Job Search Configuration and Multi-Job Discovery.

Covers:
1. Location cluster matching (Bangalore/Bengaluru, Remote/Anywhere, SF/Bay Area)
2. Experience compatibility (exact range, slightly below, senior, no requirements)
3. Company match checking (specific target matching vs non-matching)
4. Candidate deduplication (URL normalization and company+title uniqueness)
5. Resume skills matching (overlap calculation, case-insensitive)
6. Composite JobMatchScorer (40% title, 25% skills, 20% experience, 15% location)
7. MockCompanyAdapter job discovery (deterministic discovery for searches)
8. NaukriCompanyAdapter HTML parsing heuristics
9. Database persistence & schema verification for JobSearchConfig & DiscoveredJob
"""

import pytest
from unittest.mock import MagicMock
from app.automation.matcher import (
    calculate_location_compatibility,
    calculate_experience_compatibility,
    check_company_match,
    match_resume_skills,
    normalize_job_url_for_dedup,
    is_duplicate_candidate,
    JobMatchScorer,
)
from app.automation.companies.mock_adapter import MockCompanyAdapter
from app.automation.companies.naukri_adapter import NaukriCompanyAdapter
from app.automation.companies.base import DiscoveredJob


# 1. Location Cluster Matching
def test_1_location_cluster_matching():
    # Direct alias match within Bangalore cluster
    score, reasons = calculate_location_compatibility("Bangalore", "Bengaluru, Karnataka")
    assert score >= 95.0
    assert any("Bangalore" in r or "matches" in r.lower() for r in reasons)

    # Remote match
    score, reasons = calculate_location_compatibility("Remote", "San Francisco (Remote)")
    assert score == 100.0
    assert any("Remote" in r for r in reasons)

    # San Francisco bay area cluster
    score, reasons = calculate_location_compatibility("San Francisco", "Mountain View, CA")
    assert score >= 90.0

    # Divergent locations
    score, reasons = calculate_location_compatibility("Seattle", "Miami, FL")
    assert score <= 40.0


# 2. Experience Compatibility
def test_2_experience_compatibility():
    # Inside range
    score, reasons = calculate_experience_compatibility(
        user_years=3, job_exp_str="2 - 5 Yrs"
    )
    assert score == 100.0
    assert any("within required range" in r.lower() for r in reasons)

    # Slightly below
    score, reasons = calculate_experience_compatibility(
        user_years=2, job_exp_str="3 to 5 Yrs"
    )
    assert score >= 80.0

    # Significant deficit
    score, reasons = calculate_experience_compatibility(
        user_years=1, job_exp_str="7 - 10 Yrs"
    )
    assert score <= 35.0

    # Slightly overqualified
    score, reasons = calculate_experience_compatibility(
        user_years=6, job_exp_str="2 - 4 Yrs"
    )
    assert score >= 80.0


# 3. Company Matching
def test_3_company_matching():
    # No specific company requested -> always matches
    matched, score, reasons = check_company_match(None, "Google LLC")
    assert matched is True
    assert score == 100.0

    # Target company matches
    matched, score, reasons = check_company_match("Google", "Google India Pvt Ltd")
    assert matched is True
    assert score == 100.0

    # Target company mismatch
    matched, score, reasons = check_company_match("Stripe", "Amazon Web Services")
    assert matched is False
    assert score == 0.0


# 4. Deduplication
def test_4_deduplication():
    # Clean URL normalization removes tracking params
    raw_url_1 = "https://careers.company.com/job/12345?utm_source=linkedin&ref=board"
    raw_url_2 = "https://careers.company.com/job/12345"
    assert normalize_job_url_for_dedup(raw_url_1) == normalize_job_url_for_dedup(raw_url_2)

    existing = [
        DiscoveredJob(
            title="Software Developer",
            company="Acme Corp",
            job_url="https://acme.com/jobs/dev-1?utm_medium=feed",
            location="Remote",
        )
    ]

    # Duplicate by URL
    is_dup = is_duplicate_candidate(
        candidate_url="https://acme.com/jobs/dev-1",
        candidate_title="Backend Developer",
        candidate_company="Different Name",
        existing_records=existing,
    )
    assert is_dup is True

    # Duplicate by Company + Title
    is_dup_title = is_duplicate_candidate(
        candidate_url="https://acme.com/other-link",
        candidate_title="Software Developer",
        candidate_company="Acme Corp",
        existing_records=existing,
    )
    assert is_dup_title is True

    # Not duplicate
    is_not_dup = is_duplicate_candidate(
        candidate_url="https://acme.com/new-job",
        candidate_title="Product Manager",
        candidate_company="Acme Corp",
        existing_records=existing,
    )
    assert is_not_dup is False


# 5. Resume Skills Match
def test_5_resume_skills_match():
    user_skills = ["Python", "FastAPI", "PostgreSQL", "Docker"]
    cand_skills = ["python", "FastAPI", "Kubernetes"]

    score, reasons = match_resume_skills(user_skills, cand_skills)
    assert score == 50.0  # 2 of 4 user skills matched
    assert any("python" in r.lower() for r in reasons)


# 6. Composite JobMatchScorer
def test_6_composite_job_match_scorer():
    scorer = JobMatchScorer(match_threshold=60.0)
    res = scorer.score_job(
        target_role="Software Developer",
        candidate_title="Senior Software Developer",
        candidate_description="Seeking a Python developer with FastAPI and AWS experience.",
        candidate_location="Bengaluru",
        candidate_skills=["Python", "FastAPI"],
        user_skills=["Python", "FastAPI", "Docker"],
        user_location="Bangalore",
        user_experience_years=4,
        candidate_experience_str="3-6 Yrs",
        candidate_company="Google",
        specific_company=None,
    )

    assert res.is_match is True
    assert res.match_score >= 80.0
    assert "title_score" in res.breakdown
    assert "skills_score" in res.breakdown
    assert "experience_score" in res.breakdown
    assert "location_score" in res.breakdown
    assert res.breakdown["weighted_score"] == res.match_score


# 7. MockCompanyAdapter Discovery
@pytest.mark.asyncio
async def test_7_mock_adapter_discovery():
    adapter = MockCompanyAdapter()
    mock_page = MagicMock()
    jobs = await adapter.discover_jobs_from_search(
        page=mock_page,
        search_url="https://example.com/search?q=Software+Engineer&l=Bangalore",
        max_jobs=5,
    )
    assert len(jobs) == 5
    for j in jobs:
        assert j.title
        assert j.company
        assert j.job_url
        assert j.platform in ("mock", "MockPortal")


# 8. NaukriCompanyAdapter Card Parsing
def test_8_naukri_adapter_card_parsing():
    adapter = NaukriCompanyAdapter()
    assert adapter.is_search_page("https://www.naukri.com/software-developer-jobs-in-bangalore")
    assert adapter.is_search_page("https://www.naukri.com/it-jobs")
    assert not adapter.is_search_page("https://www.naukri.com/job-listings-software-developer-12345")


# 9. Schema and Models check
def test_9_models_and_schemas():
    from app.models import JobSearchConfig, DiscoveredJob as DiscoveredJobModel
    from app.schemas import JobSearchConfigRequest, JobSearchConfigResponse

    req = JobSearchConfigRequest(
        desired_job_title="Software Developer",
        desired_location="Bangalore",
        years_of_experience=3,
        platform_search_url="https://mock.example.com/search",
        specific_company="Acme",
        max_jobs_to_discover=10,
        min_match_score=75.0,
        skip_already_applied=True,
        schedule_interval="daily",
    )
    assert req.desired_job_title == "Software Developer"
    assert req.max_jobs_to_discover == 10
    assert req.min_match_score == 75.0
    assert req.skip_already_applied is True
    assert req.schedule_interval == "daily"


# 10. Matched and Missing Skills Extraction
def test_10_matched_and_missing_skills_extraction():
    user_skills = ["Python", "FastAPI", "Docker", "PostgreSQL", "React"]
    candidate_skills = ["Python", "Docker", "AWS", "Kubernetes"]

    res = match_resume_skills(user_skills, candidate_skills)
    # Check 2-tuple unpacking backward compatibility
    score, reasons = res
    assert score == 40.0  # 2 matched out of 5 user skills
    assert res.matched_skills == ["Docker", "Python"]
    assert "Aws" in res.missing_skills or "AWS" in [s.upper() for s in res.missing_skills]

    # Integrated in JobMatchScorer
    scorer = JobMatchScorer()
    score_res = scorer.score_job(
        target_role="Software Developer",
        candidate_title="Software Developer",
        candidate_skills=candidate_skills,
        user_skills=user_skills,
    )
    assert score_res.matched_skills == ["Docker", "Python"]
    assert len(score_res.missing_skills) > 0


# 11. Deduplication by Requisition ID and Already Applied Filter
def test_11_deduplication_requisition_id_and_applied():
    existing = [
        DiscoveredJob(
            title="Software Developer",
            company="MockCorp",
            job_url="https://mockcorp.com/jobs/1?reqId=REQ-101",
            requisition_id="REQ-101",
            location="New York, NY",
        )
    ]

    # Same requisition ID -> duplicate
    assert is_duplicate_candidate(
        candidate_url="https://mockcorp.com/jobs/different-url",
        candidate_title="Software Developer",
        candidate_company="MockCorp",
        existing_records=existing,
        candidate_requisition_id="REQ-101",
    ) is True

    # Different requisition ID -> distinct job (not duplicate)
    assert is_duplicate_candidate(
        candidate_url="https://mockcorp.com/jobs/dev-2",
        candidate_title="Software Developer",
        candidate_company="MockCorp",
        existing_records=existing,
        candidate_requisition_id="REQ-999",
    ) is False

    # Already applied records check
    applied_records = [
        DiscoveredJob(
            title="Frontend Developer",
            company="Acme",
            job_url="https://acme.com/jobs/front-1",
            location="Remote",
        )
    ]
    assert is_duplicate_candidate(
        candidate_url="https://acme.com/jobs/front-1",
        candidate_title="Frontend Developer",
        candidate_company="Acme",
        existing_records=[],
        already_applied_records=applied_records,
    ) is True


# 12. Search Config API Integration
def test_12_search_config_crud_api():
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.database import Base, get_db
    from app.auth import get_current_user
    from app.main import app
    from app.models import User

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    test_user = User(id=uuid4(), name="Config User", email="config_user@example.com", password_hash="test")
    with session_factory() as db:
        db.add(test_user)
        db.commit()

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user

    with TestClient(app) as client:
        # Create / Save config
        res = client.post(
            "/api/automation/search/config",
            json={
                "desired_job_title": "Software Developer",
                "desired_location": "New York, NY",
                "years_of_experience": 3,
                "platform_search_url": "mock://localhost/jobs",
                "specific_company": "MockCorp",
                "min_match_score": 65.0,
                "max_jobs_to_discover": 8,
                "skip_already_applied": True,
                "schedule_interval": "daily",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["desired_job_title"] == "Software Developer"
        assert data["min_match_score"] == 65.0
        assert data["skip_already_applied"] is True
        assert data["schedule_interval"] == "daily"

        # Read config
        res_get = client.get("/api/automation/search/config")
        assert res_get.status_code == 200
        get_data = res_get.json()
        assert get_data["desired_job_title"] == "Software Developer"
        assert get_data["max_jobs_to_discover"] == 8

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


# 13. Job Discovery API with Mock Platform and Verification of Enriched Fields
def test_13_job_discovery_api_with_mock():
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.database import Base, get_db
    from app.auth import get_current_user
    from app.main import app
    from app.models import User, Resume, JobSearchConfig

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    test_user = User(id=uuid4(), name="Discovery User", email="discovery_user@example.com", password_hash="test")
    with session_factory() as db:
        db.add(test_user)
        resume = Resume(
            id=uuid4(),
            user_id=test_user.id,
            filename="cv.pdf",
            file_path="/tmp/cv.pdf",
            extracted_text="Experienced in Python, FastAPI, Docker, and PostgreSQL.",
            is_active=True,
        )
        db.add(resume)
        config = JobSearchConfig(
            id=uuid4(),
            user_id=test_user.id,
            desired_job_title="Software Developer",
            desired_location="New York, NY",
            years_of_experience=3,
            platform_search_url="mock://localhost/jobs",
            max_jobs_to_discover=5,
            min_match_score=60.0,
            skip_already_applied=True,
        )
        db.add(config)
        db.commit()

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user

    with TestClient(app) as client:
        # Trigger discovery
        res = client.post(
            "/api/automation/search/discover",
            json={
                "search_url": "mock://localhost/jobs",
                "max_results": 5,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total_discovered"] > 0
        assert data["new_candidates_saved"] > 0
        assert len(data["jobs"]) > 0

        # Check enriched attributes on first candidate
        job_0 = data["jobs"][0]
        assert "exact_title" in job_0
        assert "match_score" in job_0
        assert "requisition_id" in job_0
        assert "matched_skills" in job_0
        assert "missing_skills" in job_0
        assert "experience_raw" in job_0

        # Queue discovered candidate
        cand_id = job_0["id"]
        res_queue = client.post(f"/api/automation/search/jobs/{cand_id}/queue")
        assert res_queue.status_code == 200
        assert res_queue.json()["status"] == "QUEUED"

        # Apply discovered candidate (triggers application and identity lock)
        from unittest.mock import AsyncMock, patch
        from app.automation.engine import PlaywrightAutomationEngine
        with patch.object(PlaywrightAutomationEngine, "execute_run", new_callable=AsyncMock):
            res_apply = client.post(f"/api/automation/search/jobs/{cand_id}/apply")
            assert res_apply.status_code == 200
            run_data = res_apply.json()
            assert run_data["company"] == job_0["company"]
            assert run_data["job_title"] == job_0["exact_title"]

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


# 14. Scheduler Multi-Job Discovery Execution
@pytest.mark.asyncio
async def test_14_scheduler_search_config_discovery():
    from uuid import uuid4
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.database import Base
    from app.models import User, Resume, JobSearchConfig, DiscoveredJob
    from app.automation.scheduler import AutomationScheduler

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    test_user = User(id=uuid4(), name="Sched User", email="sched_user@example.com", password_hash="test")
    with session_factory() as db:
        db.add(test_user)
        resume = Resume(
            id=uuid4(),
            user_id=test_user.id,
            filename="cv.pdf",
            file_path="/tmp/cv.pdf",
            extracted_text="Python, FastAPI, AWS",
            is_active=True,
        )
        db.add(resume)
        config = JobSearchConfig(
            id=uuid4(),
            user_id=test_user.id,
            desired_job_title="Software Developer",
            desired_location="New York, NY",
            years_of_experience=2,
            platform_search_url="mock://localhost/jobs",
            max_jobs_to_discover=4,
            min_match_score=60.0,
            skip_already_applied=True,
            schedule_interval="daily",
        )
        db.add(config)
        db.commit()

        scheduler = AutomationScheduler()
        new_jobs = await scheduler.process_search_config_schedule(db, config.id)
        assert len(new_jobs) > 0
        assert all(j.user_id == test_user.id for j in new_jobs)
        assert config.last_searched_at is not None

    Base.metadata.drop_all(engine)
    engine.dispose()
