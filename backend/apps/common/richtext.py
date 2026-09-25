"""
Rich-text sanitising. The editor sends HTML; it is untrusted input, so it is
reduced to an allow-list of formatting tags before it is stored. The frontend
sanitises again before rendering (defence in depth).
"""

import html
import re

import nh3

ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "code",
    "pre",
    "blockquote",
    "ul",
    "ol",
    "li",
    "a",
    "h2",
    "h3",
}
ALLOWED_ATTRIBUTES = {"a": {"href"}}
URL_SCHEMES = {"http", "https", "mailto"}

_WHITESPACE = re.compile(r"\s+")


def sanitize_html(raw: str) -> str:
    return nh3.clean(
        raw or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
        strip_comments=True,
    ).strip()


def html_to_text(clean_html: str) -> str:
    # Keep word boundaries between block elements before stripping tags.
    spaced = re.sub(r"</(p|li|h2|h3|blockquote|pre)>|<br\s*/?>", " ", clean_html)
    text = nh3.clean(spaced, tags=set())
    return _WHITESPACE.sub(" ", html.unescape(text)).strip()


def text_to_html(text: str) -> str:
    """Plain-text notes (forwarding note, assessment comment) -> safe paragraphs."""
    paragraphs = [p.strip() for p in (text or "").split("\n") if p.strip()]
    return "".join(f"<p>{html.escape(p)}</p>" for p in paragraphs)
