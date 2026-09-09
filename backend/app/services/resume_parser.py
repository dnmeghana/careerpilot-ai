from io import BytesIO

from pypdf import PdfReader


def extract_text_from_pdf(content: bytes) -> str:
    """Extract text locally; resumes are not sent to an external AI service."""
    reader = PdfReader(BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
