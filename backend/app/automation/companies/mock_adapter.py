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
        return [
            DiscoveredJob(
                title="Staff Software Engineer",
                company="MockCorp",
                url="http://127.0.0.1:8899/jobs/mock-staff-engineer",
                location="Remote - US",
                description="Lead platform architecture and agentic automation systems.",
            ),
            DiscoveredJob(
                title="Frontend Engineer",
                company="MockCorp",
                url="http://127.0.0.1:8899/jobs/mock-frontend-engineer",
                location="San Francisco, CA",
                description="Build intuitive React interfaces.",
            ),
        ]

