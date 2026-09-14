"""Safety rules, sensitive question classification, and bot/CAPTCHA guards."""

import re
from typing import NamedTuple


# Keywords signaling legal declarations and binding statements
LEGAL_KEYWORDS = (
    "certify",
    "i declare",
    "i acknowledge",
    "under penalty of perjury",
    "background check",
    "drug screen",
    "consent",
    "arbitration",
    "non-compete",
    "confidentiality agreement",
    "truthful",
    "accurate to the best of my knowledge",
    "terms and conditions",
    "signature",
)

# Keywords signaling demographic/EEO questions
DEMOGRAPHIC_KEYWORDS = (
    "gender",
    "race",
    "ethnicity",
    "veteran status",
    "disability",
    "hispanic",
    "latino",
    "equal employment",
    "eeo",
    "sexual orientation",
)

# Keywords signaling work authorization and sponsorship
SPONSORSHIP_KEYWORDS = (
    "sponsorship",
    "visa",
    "work authorization",
    "authorized to work",
    "h1b",
    "opt",
    "require sponsorship",
    "future sponsorship",
    "eligible to work",
)

# Selectors / indicators for CAPTCHA, Cloudflare Turnstile, MFA, and bot security
CAPTCHA_SELECTORS = (
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "iframe[src*='challenges.cloudflare.com']",
    ".g-recaptcha",
    ".h-captcha",
    "#cf-turnstile",
    "#challenge-stage",
    "[data-sitekey]",
    "#px-captcha",
    ".geetest_holder",
)

CAPTCHA_PAGE_TEXTS = (
    "verify you are human",
    "security check to continue",
    "checking your browser",
    "please complete the security check",
    "enter the code sent to",
    "two-factor authentication",
    "enter verification code",
)


class SafetyCheckResult(NamedTuple):
    is_safe_to_auto_fill: bool
    requires_user_confirmation: bool
    is_captcha_or_mfa: bool
    is_legal: bool
    is_demographic: bool
    is_sponsorship: bool
    reason: str


def check_element_safety(
    field_name: str,
    field_label: str,
    field_text: str = "",
    demographic_opt_in: bool = False,
    profile_has_sponsorship_info: bool = False,
) -> SafetyCheckResult:
    """Classify field safety and determine whether user confirmation is mandatory."""
    combined = f"{field_name} {field_label} {field_text}".lower()

    # Check legal declarations
    if any(k in combined for k in LEGAL_KEYWORDS):
        return SafetyCheckResult(
            is_safe_to_auto_fill=False,
            requires_user_confirmation=True,
            is_captcha_or_mfa=False,
            is_legal=True,
            is_demographic=False,
            is_sponsorship=False,
            reason="Legal or binding declaration requires explicit user confirmation.",
        )

    # Check demographic / EEO
    if any(k in combined for k in DEMOGRAPHIC_KEYWORDS):
        if not demographic_opt_in:
            return SafetyCheckResult(
                is_safe_to_auto_fill=False,
                requires_user_confirmation=True,
                is_captcha_or_mfa=False,
                is_legal=False,
                is_demographic=True,
                is_sponsorship=False,
                reason="Voluntary demographic / EEO disclosure question requires user permission.",
            )

    # Check sponsorship / work authorization
    if any(k in combined for k in SPONSORSHIP_KEYWORDS):
        if not profile_has_sponsorship_info:
            return SafetyCheckResult(
                is_safe_to_auto_fill=False,
                requires_user_confirmation=True,
                is_captcha_or_mfa=False,
                is_legal=False,
                is_demographic=False,
                is_sponsorship=True,
                reason="Sponsorship/work authorization question cannot be answered because information is not stored in your profile.",
            )

    return SafetyCheckResult(
        is_safe_to_auto_fill=True,
        requires_user_confirmation=False,
        is_captcha_or_mfa=False,
        is_legal=False,
        is_demographic=False,
        is_sponsorship=False,
        reason="Field is safe for standard profile-driven automation.",
    )


def detect_security_barrier(page_content: str) -> tuple[bool, str]:
    """Detect if page presents CAPTCHA, Cloudflare, or MFA challenge."""
    content_lower = page_content.lower()
    for text in CAPTCHA_PAGE_TEXTS:
        if text in content_lower:
            return True, f"Security challenge detected: '{text}'. Manual action required."
    return False, ""

