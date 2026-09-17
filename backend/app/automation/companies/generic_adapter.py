"""Generic Company Adapter for standard web job portals."""

import re
from typing import Any, List
from .base import BaseCompanyAdapter, FormFieldDescriptor, StepResult


class GenericCompanyAdapter(BaseCompanyAdapter):
    """Fallback adapter for generic company career sites, Greenhouse, Lever, and Workday."""

    @property
    def company_name(self) -> str:
        return "Generic"

    def can_handle_url(self, url: str) -> bool:
        # Generic adapter handles any URL as a fallback
        return True

    async def inspect_current_step(self, page: Any) -> StepResult:
        """Scan current page DOM for visible form fields, labels, and inputs."""
        fields: List[FormFieldDescriptor] = []

        # Find all interactive form inputs
        input_elements = page.locator("input:not([type='hidden']):not([type='submit']), textarea, select")
        count = await input_elements.count()

        for i in range(count):
            el = input_elements.nth(i)
            if not await el.is_visible():
                continue

            tag_name = await el.evaluate("e => e.tagName.toLowerCase()")
            input_type = await el.evaluate("e => (e.getAttribute('type') || 'text').toLowerCase()") if tag_name == "input" else tag_name

            # Determine label and accessible name
            label_text = await el.evaluate("""
                e => {
                    // 1. Associated label via for
                    if (e.id) {
                        const lbl = document.querySelector(`label[for='${e.id}']`);
                        if (lbl && lbl.innerText) return lbl.innerText.trim();
                    }
                    // 2. Closest ancestor label
                    const parentLbl = e.closest('label');
                    if (parentLbl && parentLbl.innerText) return parentLbl.innerText.trim();

                    // 3. aria-label or aria-labelledby
                    if (e.getAttribute('aria-label')) return e.getAttribute('aria-label').trim();
                    if (e.getAttribute('aria-labelledby')) {
                        const ariaEl = document.getElementById(e.getAttribute('aria-labelledby'));
                        if (ariaEl && ariaEl.innerText) return ariaEl.innerText.trim();
                    }

                    // 4. placeholder or name
                    return e.getAttribute('placeholder') || e.getAttribute('name') || '';
                }
            """)

            name_attr = await el.get_attribute("name") or ""
            id_attr = await el.get_attribute("id") or ""
            is_required = await el.evaluate("e => e.required || e.getAttribute('aria-required') === 'true'")

            # Derive standardized field_key from label/name
            combined_ident = f"{label_text} {name_attr} {id_attr}".lower()
            field_key = self._classify_field_key(combined_ident, input_type)

            options: List[str] = []
            if tag_name == "select":
                options = await el.evaluate("""
                    e => Array.from(e.options).map(o => o.text.trim()).filter(t => t.length > 0)
                """)

            # Stable selector preference
            selector = self._generate_stable_selector(id_attr, name_attr, input_type, label_text)

            descriptor = FormFieldDescriptor(
                field_key=field_key,
                label=label_text or name_attr or "Question",
                input_type=input_type,
                selector=selector,
                accessible_name=label_text,
                required=bool(is_required),
                options=options,
            )
            fields.append(descriptor)

        # Check if this is the last step or there are more steps
        has_next = await page.locator("button:has-text('Next'), button:has-text('Continue')").count() > 0
        has_submit = await page.locator("button:has-text('Submit')").count() > 0

        page_title = await page.title()
        return StepResult(
            status="in_progress",
            step_name=page_title or "Application Form",
            fields=fields,
            is_last_step=has_submit and not has_next,
            can_proceed=len(fields) > 0,
        )

    def _classify_field_key(self, text: str, input_type: str) -> str:
        """Classify input purpose into standard keys."""
        if input_type == "file" or "resume" in text or "cv" in text:
            return "resume"
        if "first name" in text or "given name" in text:
            return "first_name"
        if "last name" in text or "family name" in text or "surname" in text:
            return "last_name"
        if "full name" in text or "your name" in text or ("name" in text and "company" not in text):
            return "name"
        if "email" in text:
            return "email"
        if "phone" in text or "mobile" in text or "tel" in text:
            return "phone"
        if "linkedin" in text:
            return "linkedin_url"
        if "github" in text:
            return "github_url"
        if "portfolio" in text or "website" in text:
            return "portfolio_url"
        if "city" in text or "location" in text or "address" in text:
            return "location"
        if "sponsorship" in text or "visa" in text:
            return "requires_sponsorship"
        if "authorized" in text or "authorization" in text:
            return "work_authorization"
        if "years" in text and "experience" in text:
            return "years_of_experience"

        # Fallback to sanitized identifier
        sanitized = re.sub(r"[^a-zA-Z0-9_]+", "_", text.strip()[:40]).strip("_")
        return sanitized or f"field_{input_type}"

    def _generate_stable_selector(self, id_attr: str, name_attr: str, input_type: str, label_text: str) -> str:
        """Generate high-priority resilient selector."""
        if id_attr:
            return f"#{id_attr}"
        if name_attr:
            return f"[name='{name_attr}']"
        if label_text:
            return f"text={label_text}"
        return f"input[type='{input_type}']"

    async def discover_jobs_from_search(
        self, page: Any, search_url: str, max_jobs: int = 15
    ) -> List[DiscoveredJob]:
        """Scrape and discover jobs from a generic job search or career portal listing with pagination."""
        from urllib.parse import urljoin
        from .base import DiscoveredJob
        from ..matcher import extract_requisition_id_from_url_or_text
        from ..safety import detect_access_denied, detect_security_barrier

        discovered: List[DiscoveredJob] = []
        seen_urls = set()

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1500)
        except Exception:
            pass

        # Check for access barrier or bot detection immediately
        try:
            content = await page.content()
            page_title = await page.title()
            is_denied, denied_reason = detect_access_denied(content, page_title)
            if is_denied:
                raise PermissionError(f"Access Denied: {denied_reason}")
            is_barrier, barrier_reason = detect_security_barrier(content)
            if is_barrier:
                raise PermissionError(f"Security Barrier: {barrier_reason}")
        except PermissionError:
            raise
        except Exception:
            pass

        card_selectors = [
            "[data-job-id]",
            "[class*='job-card']",
            "[class*='job-item']",
            "[class*='job-row']",
            "[class*='job-listing']",
            "[class*='posting']",
            ".mock-job-card",
            "article",
        ]

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

            if found_cards:
                count = await found_cards.count()
                for i in range(count):
                    if len(discovered) >= max_jobs:
                        break
                    card = found_cards.nth(i)
                    try:
                        title_el = card.locator("a[href*='job'], a[href*='career'], h2, h3, h4, .title, strong").first
                        title = ""
                        job_url = ""
                        if await title_el.count() > 0:
                            title = (await title_el.inner_text()).strip()
                            job_url = await title_el.get_attribute("href") or ""

                        if not job_url:
                            a_el = card.locator("a[href]").first
                            if await a_el.count() > 0:
                                job_url = await a_el.get_attribute("href") or ""

                        if not title or len(title) < 2:
                            continue

                        if job_url and not job_url.startswith("http"):
                            job_url = urljoin(search_url, job_url)

                        if job_url and job_url in seen_urls:
                            continue

                        # Extract company, location, experience if available
                        comp_el = card.locator("[class*='company'], [class*='employer'], .company").first
                        company = self.company_name
                        if await comp_el.count() > 0:
                            raw_c = (await comp_el.inner_text()).strip()
                            if raw_c:
                                company = raw_c

                        loc_el = card.locator("[class*='location'], [class*='city'], .location").first
                        location = None
                        if await loc_el.count() > 0:
                            location = (await loc_el.inner_text()).strip()

                        exp_el = card.locator("[class*='exp'], [class*='years']").first
                        exp_str = None
                        if await exp_el.count() > 0:
                            exp_str = (await exp_el.inner_text()).strip()

                        desc_el = card.locator("p, [class*='desc'], [class*='snippet']").first
                        desc = None
                        if await desc_el.count() > 0:
                            desc = (await desc_el.inner_text()).strip()

                        skills: List[str] = []
                        tags_el = card.locator("[class*='tag'], [class*='skill'], [class*='badge'], [class*='pill'], li")
                        tag_count = await tags_el.count()
                        for t in range(min(tag_count, 8)):
                            tag_txt = (await tags_el.nth(t).inner_text()).strip()
                            if tag_txt and len(tag_txt) < 30 and tag_txt.lower() not in (title.lower(), company.lower()):
                                skills.append(tag_txt)

                        req_id = extract_requisition_id_from_url_or_text(job_url, f"{title} {desc or ''}")

                        discovered.append(
                            DiscoveredJob(
                                title=title,
                                company=company,
                                url=job_url or search_url,
                                location=location,
                                description=desc,
                                platform="portal",
                                experience_str=exp_str,
                                requisition_id=req_id,
                                skills=skills,
                            )
                        )
                        if job_url:
                            seen_urls.add(job_url)
                    except Exception:
                        continue

            if not discovered:
                # Fallback: scan for links with job in href or text
                job_links = page.locator("a[href*='/job/'], a[href*='/jobs/'], a[href*='/careers/'], a[href*='/posting/']")
                link_count = await job_links.count()
                for j in range(min(link_count, max_jobs)):
                    link = job_links.nth(j)
                    try:
                        text = (await link.inner_text()).strip()
                        href = await link.get_attribute("href") or ""
                        if href and not href.startswith("http"):
                            href = urljoin(search_url, href)

                        if text and href and href not in seen_urls and len(text) > 3:
                            seen_urls.add(href)
                            req_id = extract_requisition_id_from_url_or_text(href, text)
                            discovered.append(
                                DiscoveredJob(
                                    title=text,
                                    company=self.company_name,
                                    url=href,
                                    platform="portal",
                                    requisition_id=req_id,
                                )
                            )
                    except Exception:
                        continue

            # Attempt pagination if more jobs needed
            if len(discovered) < max_jobs:
                next_btn = page.locator("a[rel='next'], a:has-text('Next'), button:has-text('Next'), .pagination-next, a.next, button[aria-label*='Next']").first
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