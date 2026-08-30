"""
SignalAtlas LLM Prompts

Defines the prompts used for LLM-based extraction.
Each prompt is designed to:
- Extract structured data from unstructured text
- Return valid JSON matching our Pydantic schemas
- Handle edge cases gracefully
- Be provider-agnostic
"""

from typing import Dict, Any, Optional, List


# ============================================================================
# Base Prompt Template
# ============================================================================

BASE_PROMPT_TEMPLATE = """
You are an expert data extraction assistant. Your task is to extract structured information from the provided text.

## Instructions:
1. Carefully read the entire text below
2. Extract the requested information
3. Return ONLY a valid JSON object matching the specified schema
4. If information is not present or cannot be determined, use `null` for that field
5. Do NOT invent or hallucinate information
6. Do NOT add explanatory text, only the JSON
7. The JSON must be parseable and match the schema exactly

## Text to analyze:
{text}

## Schema to match:
{schema}

## Extracted data:
"""


# ============================================================================
# Startup Extraction Prompt
# ============================================================================

STARTUP_EXTRACTION_PROMPT = """
You are an expert at extracting startup information from web pages.

## Instructions:
1. Extract startup information from the provided HTML/text
2. Return ONLY a valid JSON object with the following structure:

{{
    "entity_name": string (required - the startup's canonical name),
    "description": string or null (startup description),
    "employee_count": integer or null (number of employees),
    "website": string or null (official website URL),
    "founded_year": integer or null (founding year),
    "location": string or null (physical location),
    "batch": string or null (YC batch if applicable)
}}

3. Rules:
   - "entity_name" is REQUIRED and must not be null
   - If you cannot find a value, use null (not empty string, not placeholder)
   - URLs must be complete (include https://)
   - Employee count must be a number, not a range like "10-50"
   - If a range is given, use the midpoint or null
   - Location should be a city, state, or country

## Text:
{text}

## Extracted data:
"""


# ============================================================================
# Product Extraction Prompt
# ============================================================================

PRODUCT_EXTRACTION_PROMPT = """
You are an expert at extracting product information from web pages.

## Instructions:
1. Extract product information from the provided HTML/text
2. Return ONLY a valid JSON object with the following structure:

{{
    "product_name": string (required - the product's name),
    "startup_name": string or null (startup/company name),
    "description": string or null (product description),
    "tagline": string or null (short tagline/slogan),
    "website": string or null (product website URL),
    "pricing_model": string or null (one of: FREE, FREEMIUM, PAID, ENTERPRISE),
    "tags": array of strings or null (product categories/tags),
    "upvotes": integer or null (number of upvotes/likes)
}}

3. Rules:
   - "product_name" is REQUIRED and must not be null
   - "pricing_model" must be one of: FREE, FREEMIUM, PAID, ENTERPRISE (case-sensitive)
   - If pricing is not clear, use null
   - Tags should be short (1-3 words each)
   - URLs must be complete

## Text:
{text}

## Extracted data:
"""


# ============================================================================
# Research Paper Extraction Prompt
# ============================================================================

PAPER_EXTRACTION_PROMPT = """
You are an expert at extracting research paper information from academic pages.

## Instructions:
1. Extract paper information from the provided HTML/text
2. Return ONLY a valid JSON object with the following structure:

{{
    "title": string (required - the paper's title),
    "authors": array of strings (required - list of author names),
    "paper_url": string (required - URL of the paper),
    "abstract": string or null (paper abstract),
    "published_date": string or null (ISO 8601 date: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ),
    "external_id": string or null (paper ID like arXiv ID),
    "category": string or null (primary subject category),
    "pdf_url": string or null (URL of PDF version)
}}

3. Rules:
   - "title", "authors", and "paper_url" are REQUIRED
   - "authors" must be an array, even if there's only one author
   - If author list contains "et al.", include it as-is
   - "published_date" must be in ISO 8601 format
   - If date is relative (e.g., "2 days ago"), convert to ISO 8601 or use null
   - URLs must be complete

## Text:
{text}

## Extracted data:
"""


# ============================================================================
# Job Extraction Prompt
# ============================================================================

JOB_EXTRACTION_PROMPT = """
You are an expert at extracting job posting information from web pages.

## Instructions:
1. Extract job information from the provided HTML/text
2. Return ONLY a valid JSON object with the following structure:

{{
    "company": string (required - company name),
    "role": string (required - job title/role),
    "date": string or null (ISO 8601 date: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ),
    "is_remote": boolean or null (true if remote, false if not, null if unclear),
    "role_family": string or null (one of: Engineering, Research, Design, Product, Marketing, Sales, Operations, Other),
    "location": string or null (job location),
    "description": string or null (job description text),
    "application_url": string or null (URL to apply),
    "salary_min": number or null (minimum salary),
    "salary_max": number or null (maximum salary),
    "salary_currency": string or null (3-letter currency code like USD, EUR)
}}

3. Rules:
   - "company" and "role" are REQUIRED
   - "is_remote" must be boolean (true/false) or null
   - "role_family" must be one of: Engineering, Research, Design, Product, Marketing, Sales, Operations, Other
   - "date" must be in ISO 8601 format
   - If date is relative, convert to ISO 8601 or use null
   - Salary values must be numbers (not strings like "$100K")
   - If salary is a range like "$100K-$150K", extract min and max as numbers

## Text:
{text}

## Extracted data:
"""


# ============================================================================
# News Extraction Prompt
# ============================================================================

NEWS_EXTRACTION_PROMPT = """
You are an expert at extracting news article information from web pages.

## Instructions:
1. Extract news article information from the provided HTML/text
2. Return ONLY a valid JSON object with the following structure:

{{
    "title": string (required - article title),
    "body": string (required - main article content/body),
    "published_date": string or null (ISO 8601 date: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ),
    "author": string or null (author name),
    "summary": string or null (short summary of the article),
    "image_url": string or null (URL of featured image)
}}

3. Rules:
   - "title" and "body" are REQUIRED
   - "body" should contain the main article content (not comments, ads, or navigation)
   - "published_date" must be in ISO 8601 format
   - If date is relative, convert to ISO 8601 or use null
   - "summary" should be 1-3 sentences max
   - URLs must be complete

## Text:
{text}

## Extracted data:
"""


# ============================================================================
# Entity Resolution Prompt
# ============================================================================

ENTITY_RESOLUTION_PROMPT = """
You are an expert at resolving entity names to their canonical forms.

## Instructions:
1. Given a raw entity name and a list of candidate canonical names, determine the best match
2. Return ONLY a valid JSON object with the following structure:

{{
    "canonical_name": string (required - the best matching canonical name),
    "confidence": number (required - 0.0 to 1.0, your confidence in the match),
    "reason": string (required - brief explanation of why this match)
}}

3. Rules:
   - If there's an exact match (case-insensitive), use that with confidence 1.0
   - Consider common variations (e.g., "Google LLC" vs "Google")
   - Consider legal suffixes (Inc, Corp, LLC, Ltd) as equivalent
   - Consider punctuation differences as equivalent
   - If no good match, use the raw name as canonical with low confidence

## Raw name:
{raw_name}

## Candidate canonical names:
{candidates}

## Resolution:
"""


# ============================================================================
# Chunking Prompt (for large documents)
# ============================================================================

CHUNK_EXTRACTION_PROMPT = """
You are an expert at extracting information from document chunks.

## Context:
You are processing a large document in chunks. Extract information from this chunk and return it.
The extracted data will be merged with data from other chunks.

## Instructions:
1. Extract relevant information from this chunk
2. Return ONLY a valid JSON object
3. If the information in this chunk conflicts with previous chunks, prefer the most specific/detailed value
4. Only extract information that is clearly present in this chunk

## Chunk text:
{text}

## Schema:
{schema}

## Extracted data:
"""


# ============================================================================
# Prompt Utilities
# ============================================================================

class PromptBuilder:
    """Builds prompts for LLM extraction."""

    @staticmethod
    def build_extraction_prompt(
        text: str,
        schema: str,
        context: Optional[str] = None,
    ) -> str:
        """Build a generic extraction prompt."""
        prompt = BASE_PROMPT_TEMPLATE.format(
            text=text,
            schema=schema,
        )
        if context:
            prompt = f"{context}\n\n{prompt}"
        return prompt

    @staticmethod
    def get_prompt_for_record_type(record_type: str) -> str:
        """Get the appropriate prompt for a record type."""
        prompts = {
            "startup": STARTUP_EXTRACTION_PROMPT,
            "product": PRODUCT_EXTRACTION_PROMPT,
            "paper": PAPER_EXTRACTION_PROMPT,
            "research_paper": PAPER_EXTRACTION_PROMPT,
            "job": JOB_EXTRACTION_PROMPT,
            "news": NEWS_EXTRACTION_PROMPT,
        }
        return prompts.get(record_type, BASE_PROMPT_TEMPLATE)

    @staticmethod
    def build_entity_resolution_prompt(
        raw_name: str,
        candidates: List[str],
    ) -> str:
        """Build an entity resolution prompt."""
        candidates_str = "\n".join([f"- {c}" for c in candidates])
        return ENTITY_RESOLUTION_PROMPT.format(
            raw_name=raw_name,
            candidates=candidates_str,
        )

    @staticmethod
    def build_chunk_prompt(
        text: str,
        schema: str,
    ) -> str:
        """Build a chunk extraction prompt."""
        return CHUNK_EXTRACTION_PROMPT.format(
            text=text,
            schema=schema,
        )

    @staticmethod
    def format_schema_for_prompt(schema: Dict[str, Any]) -> str:
        """Format a schema dictionary for inclusion in a prompt."""
        import json
        return json.dumps(schema, indent=2)
