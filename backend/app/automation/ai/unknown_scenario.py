"""Unknown Scenario data structure and contextual DOM extractor."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class UnknownScenario:
    """Structured, privacy-conscious snapshot of an unrecognized form field or step."""

    company: str
    url: str
    page_title: str
    current_step: str
    field_label: str
    input_type: str  # "text", "select", "radio", "checkbox", "textarea", "file"
    element_attributes: Dict[str, str] = field(default_factory=dict)
    options: List[str] = field(default_factory=list)
    nearby_text: str = ""
    screenshot_path: Optional[str] = None
    is_required: bool = False


async def extract_unknown_scenario(
    page: Any,
    element: Any,
    company: str,
    current_step: str = "Application Step",
    screenshot_path: Optional[str] = None,
) -> UnknownScenario:
    """Extract structured, sanitized context for an unknown element without dumping the whole DOM."""
    url = page.url
    page_title = await page.title()

    # Extract element properties
    info = await element.evaluate("""
        e => {
            const attrs = {};
            for (let attr of e.attributes) {
                // Sanitize: do not capture password or sensitive tokens
                if (!['value', 'data-token', 'data-auth'].includes(attr.name.toLowerCase())) {
                    attrs[attr.name] = attr.value.substring(0, 200);
                }
            }

            // Find surrounding text/legend
            let nearby = '';
            const fieldset = e.closest('fieldset');
            if (fieldset) {
                const legend = fieldset.querySelector('legend');
                if (legend) nearby = legend.innerText.trim();
            }
            if (!nearby) {
                const parent = e.closest('.form-group, .field, div');
                if (parent) nearby = parent.innerText.replace(/\\s+/g, ' ').trim().substring(0, 300);
            }

            // Options if select
            let options = [];
            if (e.tagName.toLowerCase() === 'select') {
                options = Array.from(e.options).map(o => o.text.trim()).filter(t => t.length > 0);
            }

            // Accessible label
            let label = '';
            if (e.id) {
                const lbl = document.querySelector(`label[for='${e.id}']`);
                if (lbl) label = lbl.innerText.trim();
            }
            if (!label && e.closest('label')) {
                label = e.closest('label').innerText.trim();
            }
            if (!label) {
                label = e.getAttribute('aria-label') || e.getAttribute('placeholder') || e.getAttribute('name') || 'Unknown field';
            }

            const tag = e.tagName.toLowerCase();
            const inputType = tag === 'input' ? (e.getAttribute('type') || 'text').toLowerCase() : tag;

            return {
                label: label,
                inputType: inputType,
                attrs: attrs,
                options: options,
                nearby: nearby,
                isRequired: e.required || e.getAttribute('aria-required') === 'true'
            };
        }
    """)

    return UnknownScenario(
        company=company,
        url=url,
        page_title=page_title,
        current_step=current_step,
        field_label=info.get("label", "Unknown question"),
        input_type=info.get("inputType", "text"),
        element_attributes=info.get("attrs", {}),
        options=info.get("options", []),
        nearby_text=info.get("nearby", ""),
        screenshot_path=screenshot_path,
        is_required=info.get("isRequired", False),
    )

