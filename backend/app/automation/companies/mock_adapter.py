"""Mock Company Adapter for deterministic automated testing and local test server."""

from typing import Any, List
from .base import BaseCompanyAdapter, DiscoveredJob, StepResult
from .generic_adapter import GenericCompanyAdapter


class MockCompanyAdapter(GenericCompanyAdapter):
    """Adapter for local test servers and simulated career portals."""

    @property
    def company_name(self) -> str:
        return "MockCorp"

    def can_handle_url(self, url: str) -> bool:
        return any(k in url.lower() for k in ("mockcorp", "localhost", "127.0.0.1", "mock://"))

    def discover_jobs(self, query: str = "", location: str = "") -> List[DiscoveredJob]:
        """Return simulated job postings for testing."""
        return self._get_default_mock_jobs()

    def _get_default_mock_jobs(self) -> List[DiscoveredJob]:
        return [
            DiscoveredJob(
                title="Software Developer",
                company="MockCorp",
                url="http://127.0.0.1:8899/jobs/mock-software-developer?reqId=REQ-101",
                location="New York, NY",
                description="Build modern backend systems in Python and FastAPI. Experience with Docker and PostgreSQL.",
                platform="MockPortal",
                experience_str="2-4 years",
                skills=["Python", "FastAPI", "Docker", "PostgreSQL"],
                requisition_id="REQ-101",
            ),
            DiscoveredJob(
                title="Software Developer - Backend",
                company="MockCorp",
                url="http://127.0.0.1:8899/jobs/mock-backend-developer?reqId=REQ-102",
                location="New York, NY",
                description="Develop scalable data pipelines and APIs with Docker and PostgreSQL.",
                platform="MockPortal",
                experience_str="3-5 years",
                skills=["Python", "Docker", "PostgreSQL", "AWS"],
                requisition_id="REQ-102",
            ),
            DiscoveredJob(
                title="Software Development Engineer",
                company="MockCorp",
                url="http://127.0.0.1:8899/jobs/mock-sde?reqId=REQ-103",
                location="Remote",
                description="Cloud services and distributed systems with Python and AWS.",
                platform="MockPortal",
                experience_str="1-3 years",
                skills=["Python", "AWS", "FastAPI"],
                requisition_id="REQ-103",
            ),
            DiscoveredJob(
                title="Senior Software Developer",
                company="MockCorp",
                url="http://127.0.0.1:8899/jobs/mock-senior-dev?reqId=REQ-104",
                location="San Francisco, CA",
                description="Lead platform architecture and agentic automation systems with Kubernetes.",
                platform="MockPortal",
                experience_str="5-8 years",
                skills=["Python", "Kubernetes", "Docker"],
                requisition_id="REQ-104",
            ),
            DiscoveredJob(
                title="Sales Specialist",
                company="MockCorp",
                url="http://127.0.0.1:8899/jobs/mock-sales-rep?reqId=REQ-105",
                location="New York, NY",
                description="Drive revenue growth and B2B SaaS sales outreach.",
                platform="MockPortal",
                experience_str="2-4 years",
                skills=["Salesforce", "Outreach"],
                requisition_id="REQ-105",
            ),
            DiscoveredJob(
                title="Software Developer II",
                company="MockCorp",
                url="http://127.0.0.1:8899/jobs/mock-software-dev-2?reqId=REQ-106",
                location="Bengaluru, India",
                description="Backend engineer focused on microservices and databases.",
                platform="MockPortal",
                experience_str="2-5 years",
                skills=["Python", "PostgreSQL", "Git"],
                requisition_id="REQ-106",
            ),
        ]

    async def discover_jobs_from_search(
        self, page: Any, search_url: str, max_jobs: int = 15
    ) -> List[DiscoveredJob]:
        """Discover jobs from test page or return mock jobs if page has none."""
        try:
            dom_jobs = await super().discover_jobs_from_search(page, search_url, max_jobs)
            if dom_jobs:
                return dom_jobs
        except Exception:
            pass

        return self._get_default_mock_jobs()[:max_jobs]
