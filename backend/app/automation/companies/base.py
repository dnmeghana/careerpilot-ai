"""Base Company Adapter contract and data transfer objects."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class DiscoveredJob:
    title: str
    company: str
    url: str = ""
    location: Optional[str] = None
    description: Optional[str] = None
    requisition_id: Optional[str] = None
    match_score: Optional[float] = None
    platform: str = "portal"
    experience_str: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    job_url: Optional[str] = None

    def __post_init__(self):
        if not self.url and self.job_url:
            self.url = self.job_url
        elif not self.job_url and self.url:
            self.job_url = self.url



DiscoveredJobCandidate = DiscoveredJob


@dataclass
class FormFieldDescriptor:
    field_key: str
    label: str
    input_type: str  # "text", "email", "tel", "file", "select", "checkbox", "radio", "textarea"
    selector: str
    accessible_name: Optional[str] = None
    required: bool = False
    options: List[str] = field(default_factory=list)
    current_value: Optional[str] = None
    is_sensitive: bool = False
    nearby_text: Optional[str] = None


@dataclass
class StepResult:
    status: str  # "in_progress", "completed", "unknown_scenario", "error", "captcha"
    step_name: str
    fields: List[FormFieldDescriptor] = field(default_factory=list)
    is_last_step: bool = False
    can_proceed: bool = True
    error_message: Optional[str] = None


class BaseCompanyAdapter(ABC):
    """Abstract base class for company-specific career portal adapters."""

    @property
    @abstractmethod
    def company_name(self) -> str:
        """Display name of the company."""

    @abstractmethod
    def can_handle_url(self, url: str) -> bool:
        """Return True if this adapter supports the given URL domain/pattern."""

    def discover_jobs(self, query: str = "", location: str = "") -> List[DiscoveredJob]:
        """Discover jobs matching query and location."""
        """Discover jobs matching query and location synchronously if supported."""
        return []

    async def discover_jobs_from_search(
        self, page: Any, search_url: str, max_jobs: int = 10
    ) -> List[DiscoveredJob]:
        """Discover jobs from a platform search URL using Playwright page."""
        return []

    async def open_job(self, page: Any, job_url: str) -> bool:
        """Navigate to the job posting page."""
        await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
        return True

    async def start_application(self, page: Any) -> bool:
        """Click the 'Apply' or 'Apply Now' button on the job posting."""
        import re

        apply_buttons = page.get_by_role("button", name=re.compile(r"apply", re.I))
        count = await apply_buttons.count()
        if count > 0:
            await apply_buttons.first.click()
            await page.wait_for_timeout(1000)
            return True

        apply_links = page.get_by_role("link", name=re.compile(r"apply", re.I))
        link_count = await apply_links.count()
        if link_count > 0:
            await apply_links.first.click()
            await page.wait_for_timeout(1000)
            return True

        return False

    @abstractmethod
    async def inspect_current_step(self, page: Any) -> StepResult:
        """Inspect the current page/step and return discovered form fields and state."""

    async def navigate_next(self, page: Any) -> bool:
        """Click next, continue, or proceed button."""
        import re

        next_button = page.get_by_role(
            "button",
            name=re.compile(r"next|continue|save and continue|proceed|review", re.I),
        )
        if await next_button.count() > 0:
            await next_button.first.click()
            await page.wait_for_timeout(1000)
            return True
        return False

    async def submit_application(self, page: Any) -> bool:
        """Click final submit button."""
        import re

        submit_btn = page.get_by_role(
            "button",
            name=re.compile(r"submit application|submit|send application", re.I),
        )
        if await submit_btn.count() > 0:
            await submit_btn.first.click()
            await page.wait_for_timeout(2000)
            return True
        return False

    async def detect_completion(self, page: Any) -> bool:
        """Detect whether the application has been successfully submitted."""
        body_text = (await page.content()).lower()
        success_phrases = (
            "thank you for applying",
            "application submitted",
            "application received",
            "we have received your application",
            "your application was sent",
        )
        return any(phrase in body_text for phrase in success_phrases)

    async def detect_captcha(self, page: Any) -> bool:
        """Check if a CAPTCHA or security verification prompt is visible."""
        from ..safety import detect_security_barrier, CAPTCHA_SELECTORS

        content = await page.content()
        is_blocked, _ = detect_security_barrier(content)
        if is_blocked:
            return True

        for selector in CAPTCHA_SELECTORS:
            loc = page.locator(selector)
            if await loc.count() > 0 and await loc.first.is_visible():
                return True
        return False
