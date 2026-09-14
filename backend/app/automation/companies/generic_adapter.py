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

