"""Naukri.com Platform Company Adapter."""

import logging
import re
from typing import Any, List, Optional
from urllib.parse import urljoin

from .base import BaseCompanyAdapter, DiscoveredJob, StepResult
from .generic_adapter import GenericCompanyAdapter

logger = logging.getLogger(__name__)


class NaukriCompanyAdapter(GenericCompanyAdapter):
    """Adapter for Naukri.com job board discovery and application flows."""

    @property
    def company_name(self) -> str:
        return "Naukri"

    def can_handle_url(self, url: str) -> bool:
        if not url:
            return False
        return "naukri.com" in url.lower()

    def is_search_page(self, url: str) -> bool:
        """Check if URL represents a search results or job listings directory page."""
        if not self.can_handle_url(url):
            return False
        u = url.lower()
        if "job-listings-" in u:
            return False
        return any(term in u for term in ("-jobs", "/jobs", "/search", "it-jobs", "q="))

    async def discover_jobs_from_search(
        self, page: Any, search_url: str, max_jobs: int = 15
    ) -> List[DiscoveredJob]:
        """Scrape and discover jobs from a Naukri search results URL."""
        discovered: List[DiscoveredJob] = []

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=35000)
            await page.wait_for_timeout(2000)
        except Exception as error:
            logger.warning("Error loading search URL %s: %s", search_url, error)
            # Check if page loaded partially
            pass

        # Check for bot detection, Cloudflare, or access denied
        try:
            content = await page.content()
            page_title = await page.title()
            from ..safety import detect_access_denied, detect_security_barrier
            is_denied, denied_reason = detect_access_denied(content, page_title)
            if is_denied:
                raise PermissionError(f"Access Denied on Naukri: {denied_reason}")
            is_barrier, barrier_reason = detect_security_barrier(content)
            if is_barrier:
                raise PermissionError(f"Security Barrier on Naukri: {barrier_reason}")
            if any(term in content.lower() for term in ("access denied", "blocked", "bot detection", "verify you are human", "pardon our interruption")):
                logger.error("Naukri access denied / bot detection encountered on %s", search_url)
                raise PermissionError(f"Security Barrier on Naukri: Bot detection encountered on {search_url}")
        except PermissionError:
            raise
        except Exception:
            pass

        from ..matcher import extract_requisition_id_from_url_or_text

        # Card selectors for Naukri search result page
        card_selectors = [
            ".srp-jobtuple-wrapper",
            "article.jobTuple",
            ".cust-job-tuple",
            ".jobTuple",
            "[data-job-id]",
            "div.tuple",
        ]

        seen_urls = set()
        current_page = 1
        max_pages = 5

        while len(discovered) < max_jobs and current_page <= max_pages:
            found_cards = None
            for sel in card_selectors:
                loc = page.locator(sel)
                count = await loc.count()
                if count > 0:
                    found_cards = loc
                    break

            if not found_cards and current_page == 1:
                logger.info("No Naukri job cards matched with primary selectors; attempting fallback generic discovery.")
                return await super().discover_jobs_from_search(page, search_url, max_jobs)

            if found_cards:
                count = await found_cards.count()
                for i in range(count):
                    if len(discovered) >= max_jobs:
                        break
                    card = found_cards.nth(i)
                    try:
                        # Title & URL
                        title_el = card.locator("a.title, .title a, a[title], .title").first
                        title = ""
                        job_url = ""
                        if await title_el.count() > 0:
                            title = (await title_el.inner_text()).strip()
                            job_url = await title_el.get_attribute("href") or ""

                        if not title:
                            continue

                        if job_url and not job_url.startswith("http"):
                            job_url = urljoin("https://www.naukri.com", job_url)

                        if job_url and job_url in seen_urls:
                            continue

                        # Company
                        comp_el = card.locator("a.subTitle, .subTitle, .comp-name, a.comp-name").first
                        company = "Naukri Listing"
                        if await comp_el.count() > 0:
                            raw_comp = (await comp_el.inner_text()).strip()
                            if raw_comp:
                                company = raw_comp

                        # Location
                        loc_el = card.locator(".loc-wrap, .loc, .location, [class*='loc']").first
                        location: Optional[str] = None
                        if await loc_el.count() > 0:
                            location = (await loc_el.inner_text()).strip()

                        # Experience
                        exp_el = card.locator(".exp-wrap, .exp, .experience, [class*='exp']").first
                        experience_str: Optional[str] = None
                        if await exp_el.count() > 0:
                            experience_str = (await exp_el.inner_text()).strip()

                        # Description / snippet
                        desc_el = card.locator(".job-desc, .job-description, [class*='desc']").first
                        description: Optional[str] = None
                        if await desc_el.count() > 0:
                            description = (await desc_el.inner_text()).strip()

                        # Skills
                        skills: List[str] = []
                        tags_el = card.locator(".tags-gt li, .tag-li, ul.tags li, [class*='tag']")
                        tag_count = await tags_el.count()
                        for t in range(min(tag_count, 10)):
                            tag_text = (await tags_el.nth(t).inner_text()).strip()
                            if tag_text:
                                skills.append(tag_text)

                        req_id = extract_requisition_id_from_url_or_text(job_url, f"{title} {description or ''}")

                        discovered.append(
                            DiscoveredJob(
                                title=title,
                                company=company,
                                url=job_url or search_url,
                                location=location,
                                description=description,
                                platform="Naukri",
                                experience_str=experience_str,
                                skills=skills,
                                requisition_id=req_id,
                            )
                        )
                        if job_url:
                            seen_urls.add(job_url)
                    except Exception as card_err:
                        logger.debug("Failed parsing Naukri job card %d: %s", i, card_err)
                        continue

            if len(discovered) < max_jobs:
                next_btn = page.locator("a.fright, a:has-text('Next'), .styles_btn__[class*='next'], a[aria-label*='Next']").first
                if await next_btn.count() > 0 and await next_btn.is_visible():
                    try:
                        await next_btn.click()
                        await page.wait_for_timeout(2000)
                        current_page += 1
                        continue
                    except Exception:
                        break
                else:
                    break
            else:
                break

        return discovered
