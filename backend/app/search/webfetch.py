"""Fetch plain text content from a URL."""
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


def fetch_url(url: str, timeout: int = 15, max_chars: int = 12000) -> str:
    """Fetch a URL and return clean text.

    Returns an empty string on failure or non-HTML content.
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""

    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                )
            },
        )
        response.raise_for_status()
    except Exception:
        return ""

    content_type = response.headers.get("Content-Type", "").lower()
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        # For non-HTML, attempt to strip markdown-ish markup lightly.
        text = response.text
        text = re.sub(r"<[^>]+>", "", text)
        return text[:max_chars].strip()

    soup = BeautifulSoup(response.text, "lxml")
    # Remove script and style tags.
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    # Collapse whitespace.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)
    return text[:max_chars].strip()
