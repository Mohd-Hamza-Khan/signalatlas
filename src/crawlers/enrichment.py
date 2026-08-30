"""
SignalAtlas GitHub Enrichment

Provides enrichment of research papers with GitHub data:
- Repository verification
- Star count
- Match confidence calculation
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from structlog import get_logger

from ..crawlers.github import github_crawler
from ..utils.hashing import hasher

logger = get_logger(__name__)


class GitHubEnricher:
    """
    Enriches research papers with GitHub repository data.

    For each paper:
    1. Extract candidate GitHub URLs from paper metadata
    2. Verify repository exists
    3. Verify relevance
    4. Fetch star count
    5. Store stars + fetched_at
    """

    def __init__(self):
        self.crawler = github_crawler

    async def enrich_paper(
        self,
        paper_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Enrich a paper with GitHub data.

        Args:
            paper_data: Paper data dictionary

        Returns:
            Enriched paper data
        """
        # Extract candidate URLs
        candidate_urls = self._extract_candidate_urls(paper_data)

        if not candidate_urls:
            # No GitHub URLs found
            return {
                **paper_data,
                "github_url": None,
                "github_stars": None,
                "github_match_confidence": None,
            }

        # Verify and find best match
        best_match = await self._find_best_match(candidate_urls, paper_data)

        if best_match:
            repo_url, confidence = best_match
            stars = await self.crawler.get_star_count(repo_url)

            return {
                **paper_data,
                "github_url": repo_url,
                "github_stars": stars,
                "github_match_confidence": round(confidence, 4),
            }

        return {
            **paper_data,
            "github_url": None,
            "github_stars": None,
            "github_match_confidence": None,
        }

    async def enrich_batch(
        self,
        papers: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Enrich multiple papers with GitHub data.

        Args:
            papers: List of paper data dictionaries

        Returns:
            List of enriched paper data
        """
        results = []
        for i, paper in enumerate(papers):
            try:
                enriched = await self.enrich_paper(paper)
                results.append(enriched)
                logger.info(
                    "GitHub enrichment",
                    progress=f"{i+1}/{len(papers)}",
                    paper=paper.get("title", "Unknown")[:50],
                )
            except Exception as e:
                logger.error(
                    "GitHub enrichment failed",
                    paper=paper.get("title", "Unknown")[:50],
                    error=str(e),
                )
                results.append(paper)

        return results

    def _extract_candidate_urls(self, paper_data: Dict[str, Any]) -> List[str]:
        """
        Extract candidate GitHub URLs from paper data.

        Checks:
        - github_url field
        - Text content
        - Metadata
        """
        urls = []

        # Check explicit github_url field
        if paper_data.get("github_url"):
            urls.append(paper_data["github_url"])

        # Check text content
        text_fields = ["abstract", "description", "body", "content"]
        for field in text_fields:
            text = paper_data.get(field)
            if text:
                urls.extend(self.crawler.extract_repo_urls(text))

        # Check metadata
        metadata = paper_data.get("metadata")
        if metadata:
            if isinstance(metadata, dict):
                if metadata.get("github_url"):
                    urls.append(metadata["github_url"])
            elif isinstance(metadata, str):
                urls.extend(self.crawler.extract_repo_urls(metadata))

        # Deduplicate and normalize
        urls = list(set(urls))
        urls = [self.crawler.normalize_repo_url(u) for u in urls]

        return urls

    async def _find_best_match(
        self,
        candidate_urls: List[str],
        paper_data: Dict[str, Any],
    ) -> Optional[Tuple[str, float]]:
        """
        Find the best matching repository.

        Args:
            candidate_urls: List of candidate GitHub URLs
            paper_data: Paper data for relevance checking

        Returns:
            Tuple of (best_url, confidence) or None
        """
        if not candidate_urls:
            return None

        # Verify each URL
        valid_repos = []
        for url in candidate_urls:
            exists = await self.crawler.verify_repository(url)
            if exists:
                confidence = self._calculate_confidence(url, paper_data)
                valid_repos.append((url, confidence))

        if not valid_repos:
            return None

        # Sort by confidence
        valid_repos.sort(key=lambda x: x[1], reverse=True)

        return valid_repos[0]

    def _calculate_confidence(
        self,
        repo_url: str,
        paper_data: Dict[str, Any],
    ) -> float:
        """
        Calculate match confidence between repository and paper.

        Args:
            repo_url: GitHub repository URL
            paper_data: Paper data

        Returns:
            Confidence score (0.0 to 1.0)
        """
        confidence = 0.5  # Base confidence

        # Extract repo name
        from urllib.parse import urlparse
        parsed = urlparse(repo_url)
        repo_path = parsed.path.strip("/")
        repo_name = repo_path.split("/")[-1].lower()

        # Check if repo name matches paper title
        title = paper_data.get("title", "").lower()
        if repo_name in title or title in repo_name:
            confidence += 0.3

        # Check if repo description matches paper abstract
        abstract = paper_data.get("abstract", "").lower()
        # Would need to fetch repo description for this

        # Check if repo owner matches paper authors
        authors = paper_data.get("authors", [])
        if authors:
            for author in authors:
                if author.lower() in repo_path.lower():
                    confidence += 0.1

        # Cap at 1.0
        return min(confidence, 1.0)

    async def verify_and_enrich(
        self,
        github_url: str,
    ) -> Dict[str, Any]:
        """
        Verify a GitHub URL and get enrichment data.

        Args:
            github_url: GitHub repository URL

        Returns:
            Enrichment data with stars, description, etc.
        """
        repo = await self.crawler.get_repository(github_url)

        if not repo:
            return {
                "github_url": None,
                "github_stars": None,
                "github_description": None,
                "github_fetched_at": None,
            }

        return {
            "github_url": github_url,
            "github_stars": repo.get("stargazers_count"),
            "github_description": repo.get("description"),
            "github_fetched_at": datetime.utcnow().isoformat(),
        }


# Singleton instance
github_enricher = GitHubEnricher()
