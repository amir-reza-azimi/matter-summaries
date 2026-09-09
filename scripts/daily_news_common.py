#!/usr/bin/env python3
"""Shared schema and validation rules for the daily Matter news brief."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse


MAX_STORIES = 21
MIN_STORIES_WITHOUT_NOTE = 5
ALLOWED_CATEGORIES = {"berlin", "germany", "world", "economy", "technology", "business", "investment", "ai"}
ALLOWED_IMPORTANCE = {"major", "notable", "watch"}
ALLOWED_TIERS = {"primary", "wire", "public-service", "established"}
READER_LANGUAGE = "en"

# Keep the list short and auditable. A live run must reject a new source until it is
# deliberately added here with its tier and an independent editorial group.
SOURCE_POLICY = {
    "berlin.de": ("primary", "Berlin Senate"),
    "bvg.de": ("primary", "BVG"),
    "bundestag.de": ("primary", "German Bundestag"),
    "bundesregierung.de": ("primary", "German Federal Government"),
    "bundeswahlleiterin.de": ("primary", "Federal Returning Officer"),
    "destatis.de": ("primary", "Federal Statistical Office"),
    "bundesbank.de": ("primary", "Deutsche Bundesbank"),
    "europa.eu": ("primary", "European Union"),
    "reuters.com": ("wire", "Reuters"),
    "apnews.com": ("wire", "Associated Press"),
    "tagesschau.de": ("public-service", "ARD Tagesschau"),
    "deutschlandfunk.de": ("public-service", "Deutschlandradio"),
    "rbb24.de": ("public-service", "RBB"),
    "bbc.com": ("public-service", "BBC"),
    "ft.com": ("established", "Financial Times"),
    "handelsblatt.com": ("established", "Handelsblatt"),
    "openai.com": ("primary", "OpenAI"),
    "anthropic.com": ("primary", "Anthropic"),
    "ai.google": ("primary", "Google DeepMind"),
    "microsoft.com": ("primary", "Microsoft"),
    "nvidia.com": ("primary", "NVIDIA"),
}


def domain_for(url: str) -> str:
    domain = urlparse(url).netloc.lower().split(":")[0]
    return domain[4:] if domain.startswith("www.") else domain


def policy_for(url: str) -> tuple[str, str] | None:
    domain = domain_for(url)
    for allowed, policy in SOURCE_POLICY.items():
        if domain == allowed or domain.endswith("." + allowed):
            return policy
    return None


def sentence_count(text: str) -> int:
    return sum(text.count(mark) for mark in (".", "!", "?"))


def is_iso_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (TypeError, ValueError):
        return False


def validate_record(record: dict, prior_stories: dict[str, dict] | None = None) -> list[str]:
    errors: list[str] = []
    prior_stories = prior_stories or {}

    if record.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    try:
        datetime.strptime(record.get("date", ""), "%Y-%m-%d")
    except (TypeError, ValueError):
        errors.append("date must use YYYY-MM-DD")
    if not str(record.get("title", "")).startswith("Daily Brief"):
        errors.append("title must start with 'Daily Brief'")
    window = record.get("window") or {}
    if not is_iso_datetime(window.get("start", "")) or not is_iso_datetime(window.get("end", "")):
        errors.append("window.start and window.end must be ISO datetimes")

    stories = record.get("stories")
    if not isinstance(stories, list) or not stories or len(stories) > MAX_STORIES:
        errors.append(f"stories must contain 1 to {MAX_STORIES} entries")
        return errors
    if len(stories) < MIN_STORIES_WITHOUT_NOTE and not record.get("selection_note"):
        errors.append("briefs with fewer than 5 stories need a selection_note explaining why they were not padded")

    ids: set[str] = set()
    total_words = 0
    for index, story in enumerate(stories, start=1):
        prefix = f"story {index}"
        story_id = story.get("id")
        if not isinstance(story_id, str) or not story_id:
            errors.append(f"{prefix}: id is required")
        elif story_id in ids:
            errors.append(f"{prefix}: duplicate story id {story_id}")
        else:
            ids.add(story_id)
        if story.get("category") not in ALLOWED_CATEGORIES:
            errors.append(f"{prefix}: unsupported category")
        if story.get("importance") not in ALLOWED_IMPORTANCE:
            errors.append(f"{prefix}: unsupported importance")
        if story.get("category") == "ai" and story.get("importance") != "major":
            errors.append(f"{prefix}: daily AI stories must be major")
        title = str(story.get("title", "")).strip()
        summary = str(story.get("summary", "")).strip()
        if not title or not summary:
            errors.append(f"{prefix}: title and summary are required")
        if sentence_count(summary) > 2:
            errors.append(f"{prefix}: summary may contain at most two sentences")
        total_words += len((title + " " + summary).split())

        sources = story.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append(f"{prefix}: at least one English-language direct source is required")
            continue
        groups: set[str] = set()
        has_primary = False
        has_non_primary = False
        for source in sources:
            if source.get("language") != READER_LANGUAGE:
                errors.append(f"{prefix}: every Matter source must declare language 'en'")
            url = source.get("url", "")
            if urlparse(url).scheme != "https":
                errors.append(f"{prefix}: source URL must use HTTPS")
                continue
            policy = policy_for(url)
            if policy is None:
                errors.append(f"{prefix}: source domain is not in the approved policy: {domain_for(url)}")
                continue
            expected_tier, expected_group = policy
            if source.get("publisher") != expected_group:
                errors.append(f"{prefix}: publisher does not match policy for {domain_for(url)}")
            if source.get("tier") != expected_tier or source.get("independent_group") != expected_group:
                errors.append(f"{prefix}: source tier or editorial group does not match policy for {domain_for(url)}")
            groups.add(expected_group)
            has_primary = has_primary or expected_tier == "primary"
            has_non_primary = has_non_primary or expected_tier != "primary"
        if story.get("importance") == "major" and (len(groups) < 2 or not (has_primary and has_non_primary) and len(groups) < 2):
            errors.append(f"{prefix}: major stories require two independent approved sources")

        continuation = story.get("continuation") or {}
        prior = prior_stories.get(story_id)
        if prior and not continuation.get("material_update"):
            errors.append(f"{prefix}: repeated story needs continuation.material_update")
        if continuation.get("material_update") and len(str(continuation.get("material_update"))) < 20:
            errors.append(f"{prefix}: material_update must name the new development")

    if total_words > 850:
        errors.append(f"brief is {total_words} words; maximum is 850 for a five-minute read")
    return errors
