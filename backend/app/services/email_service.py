"""Email service abstraction for CareerPilot AI.

Provides a clean interface for email delivery, decoupling business logic
from concrete SMTP, SendGrid, SES, or local console delivery mechanisms.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, NamedTuple

logger = logging.getLogger(__name__)


class SentEmailRecord(NamedTuple):
    to_email: str
    subject: str
    body: str
    reset_url: str


class BaseEmailService(ABC):
    @abstractmethod
    def send_password_reset_email(self, to_email: str, reset_url: str) -> None:
        """Send password reset instructions containing the reset URL."""
        pass


class ConsoleEmailService(BaseEmailService):
    """Local development email delivery handler.

    Outputs formatted email details to logging and retains sent records
    in memory for testing/verification.
    """

    def __init__(self) -> None:
        self.sent_emails: List[SentEmailRecord] = []

    def send_password_reset_email(self, to_email: str, reset_url: str) -> None:
        subject = "Reset your CareerPilot password"
        body = (
            f"Hello,\n\n"
            f"We received a request to reset your CareerPilot AI password.\n\n"
            f"Use the link below to set a new password (valid for 15 minutes):\n"
            f"{reset_url}\n\n"
            f"If you did not request this password reset, you can safely ignore this message.\n\n"
            f"— The CareerPilot AI Team"
        )

        record = SentEmailRecord(
            to_email=to_email,
            subject=subject,
            body=body,
            reset_url=reset_url,
        )
        self.sent_emails.append(record)

        logger.info(
            "\n" + "=" * 70 + "\n"
            "CAREERPILOT PASSWORD RESET EMAIL (LOCAL DEVELOPMENT)\n"
            f"To: {to_email}\n"
            f"Subject: {subject}\n"
            f"Reset Link: {reset_url}\n"
            f"Valid For: 15 minutes\n"
            + "=" * 70
        )


_email_service: BaseEmailService = ConsoleEmailService()


def get_email_service() -> BaseEmailService:
    """Return configured email service provider instance."""
    return _email_service
