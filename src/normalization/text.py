"""
SignalAtlas Text Normalization

Provides utilities for normalizing text content:
- HTML cleanup
- Title extraction
- Metadata extraction
- Whitespace normalization
- Content hashing
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from structlog import get_logger

logger = get_logger(__name__)


class TextNormalizer:
    """
    Normalizes text content for consistent processing.
    """

    @staticmethod
    def clean_html(html: str) -> str:
        """
        Clean HTML by removing unwanted elements.

        Removes:
        - script tags
        - style tags
        - navigation
        - footer
        - ads
        - comments
        - excessive whitespace
        """
        if not html or not html.strip():
            return ""

        soup = BeautifulSoup(html, "lxml")

        # Remove script and style tags
        for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
            tag.decompose()

        # Remove common ad/analytics elements
        for tag in soup.find_all(
            class_=re.compile(
                r"(ad|ads|advertisement|analytics|tracking|banner|sidebar|navbar|nav)",
                re.I,
            )
        ):
            tag.decompose()

        # Remove elements with ad-related IDs
        for tag in soup.find_all(
            id=re.compile(r"(ad|ads|advertisement|analytics|tracking)", re.I)
        ):
            tag.decompose()

        # Remove navigation elements
        nav = soup.find("nav")
        if nav:
            nav.decompose()

        # Remove footer
        footer = soup.find("footer")
        if footer:
            footer.decompose()

        # Remove header (but keep main content)
        header = soup.find("header")
        if header:
            header.decompose()

        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Get text content
        text = soup.get_text()

        # Clean up whitespace
        text = TextNormalizer.normalize_whitespace(text)

        return text

    @staticmethod
    def extract_title(html: str) -> str:
        """Extract the main title from HTML."""
        if not html or not html.strip():
            return ""

        soup = BeautifulSoup(html, "lxml")

        # Try to get the title tag
        title = soup.title
        if title and title.string:
            return title.string.strip()

        # Try to get h1
        h1 = soup.find("h1")
        if h1 and h1.get_text().strip():
            return h1.get_text().strip()

        # Try to get the first heading
        for tag in ["h1", "h2", "h3"]:
            heading = soup.find(tag)
            if heading and heading.get_text().strip():
                return heading.get_text().strip()

        # Fallback: first non-empty text
        for string in soup.stripped_strings:
            if string and len(string) > 10:
                return string[:200]

        return "Untitled"

    @staticmethod
    def extract_metadata(html: str) -> Dict[str, Any]:
        """
        Extract metadata from HTML.

        Extracts:
        - OpenGraph tags
        - JSON-LD
        - Meta tags
        - Canonical URL
        """
        metadata: Dict[str, Any] = {}

        if not html or not html.strip():
            return metadata

        soup = BeautifulSoup(html, "lxml")

        # Extract OpenGraph tags
        og_tags = soup.find_all(property=re.compile(r"^og:", re.I))
        for tag in og_tags:
            if tag.get("property") and tag.get("content"):
                key = tag["property"][3:].lower()  # Remove "og:" prefix
                metadata[f"og_{key}"] = tag["content"]

        # Extract JSON-LD
        json_ld = soup.find_all(type="application/ld+json")
        for script in json_ld:
            if script.string:
                try:
                    import json
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        metadata["json_ld"] = data
                    elif isinstance(data, list) and len(data) > 0:
                        metadata["json_ld"] = data[0]
                except Exception as e:
                    logger.warning("Failed to parse JSON-LD", error=str(e))

        # Extract meta tags
        meta_tags = soup.find_all("meta")
        for tag in meta_tags:
            name = tag.get("name") or tag.get("http-equiv")
            if name:
                name = name.lower()
                content = tag.get("content")
                if content:
                    metadata[f"meta_{name}"] = content

        # Extract canonical URL
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            metadata["canonical_url"] = canonical["href"]

        # Extract date from various sources
        date = TextNormalizer._extract_date_from_metadata(metadata)
        if date:
            metadata["published_date"] = date

        return metadata

    @staticmethod
    def _extract_date_from_metadata(metadata: Dict[str, Any]) -> Optional[str]:
        """Extract date from metadata."""
        # Try JSON-LD date
        json_ld = metadata.get("json_ld")
        if json_ld:
            if isinstance(json_ld, dict):
                date = json_ld.get("datePublished") or json_ld.get("dateCreated")
                if date:
                    return date

        # Try OpenGraph date
        og_date = metadata.get("og_published_time") or metadata.get("og_published")
        if og_date:
            return og_date

        # Try meta tags
        meta_date = metadata.get("meta_published") or metadata.get("meta_date")
        if meta_date:
            return meta_date

        return None

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """
        Normalize whitespace in text.

        - Collapses multiple spaces to single space
        - Removes leading/trailing whitespace
        - Preserves line breaks (collapses multiple to single)
        """
        if not text:
            return ""

        # Replace multiple newlines with single
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Replace multiple spaces with single (but preserve newlines)
        text = re.sub(r"[ \t]+", " ", text)

        # Remove spaces before/after newlines
        text = re.sub(r"\n \n", "\n\n", text)
        text = re.sub(r"\n ", "\n", text)
        text = re.sub(r" \n", "\n", text)

        # Strip leading/trailing whitespace
        text = text.strip()

        return text

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Normalize a name for comparison.

        - Lowercase
        - Remove punctuation
        - Remove legal suffixes
        - Normalize whitespace
        """
        if not name:
            return ""

        # Lowercase
        name = name.lower()

        # Remove punctuation (keep apostrophes and hyphens)
        name = re.sub(r"[^\w\s\-']", "", name)

        # Remove legal suffixes
        suffixes = [
            r"\binc\b",
            r"\bincorporated\b",
            r"\bcorp\b",
            r"\bcorporation\b",
            r"\bllc\b",
            r"\blimited\b",
            r"\bltd\b",
            r"\bco\b",
            r"\bcompany\b",
            r"\bthe\b",
            r"\bgroup\b",
            r"\bholdings\b",
        ]
        for suffix in suffixes:
            name = re.sub(suffix, "", name)

        # Normalize whitespace
        name = TextNormalizer.normalize_whitespace(name)

        # Strip
        name = name.strip()

        return name

    @staticmethod
    def extract_main_content(html: str) -> str:
        """
        Extract the main content from HTML.

        Uses multiple strategies to find the main content:
        1. Look for main, article, or content divs
        2. Look for largest text block
        3. Fallback to cleaned HTML
        """
        if not html or not html.strip():
            return ""

        soup = BeautifulSoup(html, "lxml")

        # Try to find main content area
        main_selectors = [
            "main",
            "article",
            ".main",
            ".content",
            ".article",
            ".post",
            "[role=main]",
            "#content",
            "#main",
        ]

        for selector in main_selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text()
                if len(text.strip()) > 100:
                    return TextNormalizer.normalize_whitespace(text)

        # Try to find largest text block
        paragraphs = soup.find_all("p")
        if paragraphs:
            text = "\n\n".join(p.get_text().strip() for p in paragraphs)
            return TextNormalizer.normalize_whitespace(text)

        # Fallback to cleaned HTML
        return TextNormalizer.clean_html(html)

    @staticmethod
    def truncate_text(text: str, max_length: int = 10000) -> str:
        """
        Truncate text to maximum length.

        Tries to preserve semantic boundaries (paragraphs, sentences).
        """
        if not text or len(text) <= max_length:
            return text

        # Try to truncate at paragraph boundary
        paragraphs = text.split("\n\n")
        truncated = []
        current_length = 0

        for para in paragraphs:
            para_length = len(para)
            if current_length + para_length > max_length:
                # Add as much as we can from this paragraph
                remaining = max_length - current_length
                if remaining > 0:
                    truncated.append(para[:remaining])
                break
            truncated.append(para)
            current_length += para_length + 2  # +2 for the \n\n
        return "\n\n".join(truncated)


# Singleton instance
normalizer = TextNormalizer()


# BeautifulSoup Comment class for type checking
from bs4 import Comment
