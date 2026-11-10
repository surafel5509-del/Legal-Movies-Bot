from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import quote

import aiohttp

from bot.config import settings
from bot.services.license_verification import verify_archive_rights

ADVANCED_URL = "https://archive.org/advancedsearch.php"
DETAIL_URL = "https://archive.org/metadata/{identifier}"


class ArchiveAPI:
    """Internet Archive movie discovery with broad matching and a strict rights gate."""

    def __init__(self, session: aiohttp.ClientSession):
        self.http = session
        self._cache: dict[tuple[str, int], tuple[float, list[dict]]] = {}
        self._lock = asyncio.Lock()

    async def _json(self, url: str, *, params: dict | None = None) -> dict:
        timeout = aiohttp.ClientTimeout(total=settings.request_timeout_seconds)
        for attempt in range(3):
            try:
                async with self.http.get(url, params=params, timeout=timeout) as response:
                    response.raise_for_status()
                    return await response.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError):
                if attempt == 2:
                    raise
                await asyncio.sleep(0.4 * (attempt + 1))

    async def _search_docs(self, expression: str, page: int) -> list[dict]:
        params = {
            "q": expression,
            "fl[]": ["identifier", "title", "year", "description", "licenseurl", "publicdate", "downloads"],
            "sort[]": "downloads desc",
            "rows": str(max(25, min(100, settings.archive_page_size * 5))),
            "page": str(page + 1),
            "output": "json",
        }
        payload = await self._json(ADVANCED_URL, params=params)
        return payload.get("response", {}).get("docs", [])

    async def search(self, query: str, page: int = 0) -> list[dict]:
        """Search phrase, all title terms, then individual title terms; show only licensed results."""
        query = re.sub(r"[^\w\s'-]", " ", query, flags=re.UNICODE).strip()[:100]
        query = re.sub(r"\s+", " ", query)
        if not query:
            return []
        page = max(0, page)
        key = (query.casefold(), page)
        async with self._lock:
            cached = self._cache.get(key)
            if cached and cached[0] > asyncio.get_running_loop().time():
                return cached[1]

        phrase = _lucene_phrase(query)
        terms = [term for term in re.findall(r"[\w'-]+", query, flags=re.UNICODE) if len(term) > 1]
        strategies = [f'mediatype:movies AND (title:"{phrase}" OR description:"{phrase}")']
        if len(terms) > 1:
            all_terms = " AND ".join(f'title:{_lucene_term(term)}' for term in terms)
            strategies.append(f"mediatype:movies AND ({all_terms})")
        if terms:
            any_terms = " OR ".join(f'title:{_lucene_term(term)}' for term in terms)
            strategies.append(f"mediatype:movies AND ({any_terms})")

        docs_by_id: dict[str, dict] = {}
        successful_strategies = 0
        last_error: Exception | None = None
        for expression in strategies:
            try:
                docs = await self._search_docs(expression, 0)
                successful_strategies += 1
                for doc in docs:
                    identifier = str(doc.get("identifier") or "").strip()
                    if identifier:
                        docs_by_id.setdefault(identifier, doc)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
                last_error = exc
                continue
        if successful_strategies == 0 and last_error is not None:
            raise last_error

        query_terms = {term.casefold() for term in terms}
        ranked: list[tuple[int, int, dict]] = []
        for doc in docs_by_id.values():
            rights_ok, license_label, license_url = verify_archive_rights(doc)
            if not rights_ok:
                continue
            identifier = str(doc["identifier"])
            title = str(doc.get("title") or identifier)
            score = _match_score(query, query_terms, title, _plain(doc.get("description")))
            ranked.append((score, _int_or_none(doc.get("downloads")) or 0, {
                "identifier": identifier,
                "title": title[:500],
                "year": _year(doc.get("year")),
                "description": _plain(doc.get("description")),
                "poster_url": f"https://archive.org/services/img/{quote(identifier)}",
                "license": license_label,
                "license_url": license_url,
                "source_url": f"https://archive.org/details/{quote(identifier)}",
            }))
        ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
        start = page * settings.archive_page_size
        results = [item for _, _, item in ranked[start:start + settings.archive_page_size]]
        async with self._lock:
            self._cache[key] = (asyncio.get_running_loop().time() + settings.cache_ttl_seconds, results)
        return results

    async def details(self, identifier: str) -> dict | None:
        payload = await self._json(DETAIL_URL.format(identifier=quote(identifier, safe="")))
        metadata = payload.get("metadata", {})
        files = payload.get("files", [])
        allowed, label, license_url = verify_archive_rights(metadata)
        if not allowed:
            return None
        selected = []
        for item in files:
            name = str(item.get("name", ""))
            if item.get("private") == "true" or name.startswith("_"):
                continue
            if not name.lower().endswith((".mp4", ".webm", ".m4v", ".ogv")):
                continue
            size = _int_or_none(item.get("size"))
            selected.append({
                "filename": name,
                "format": name.rsplit(".", 1)[-1].upper(),
                "resolution": _resolution(name),
                "file_size": size,
                "download_url": f"https://archive.org/download/{quote(identifier)}/{quote(name)}",
                "codec": None,
            })
        selected.sort(key=lambda f: (f["format"] != "MP4", -(f["file_size"] or 0)))
        return {
            "identifier": identifier,
            "title": str(metadata.get("title") or identifier)[:500],
            "description": _plain(metadata.get("description")),
            "year": _year(metadata.get("year")),
            "genre": _first(metadata.get("genre")),
            "language": _first(metadata.get("language")),
            "runtime": metadata.get("runtime"),
            "poster_url": f"https://archive.org/services/img/{quote(identifier)}",
            "license": label,
            "license_url": license_url,
            "source_url": f"https://archive.org/details/{quote(identifier)}",
            "files": selected,
            "raw": {k: v for k, v in metadata.items() if k not in {"identifier"}},
        }


def _lucene_phrase(value: str) -> str:
    return re.sub(r'([+\-!(){}\[\]^"~*?:\\/])', r"\\\1", value)


def _lucene_term(value: str) -> str:
    return re.sub(r'([+\-!(){}\[\]^"~*?:\\/])', r"\\\1", value)


def _match_score(query: str, terms: set[str], title: str, description: str) -> int:
    normalized_title = re.sub(r"[^\w]+", " ", title.casefold()).strip()
    normalized_query = re.sub(r"[^\w]+", " ", query.casefold()).strip()
    title_terms = set(normalized_title.split())
    score = len(terms & title_terms) * 10
    if normalized_query and normalized_query in normalized_title:
        score += 100
    elif normalized_title and normalized_title in normalized_query:
        score += 35
    description_terms = set(re.sub(r"[^\w]+", " ", description.casefold()).split())
    score += len(terms & description_terms)
    return score


def _year(value: Any) -> int | None:
    match = re.search(r"\b(18|19|20)\d{2}\b", str(value or ""))
    return int(match.group()) if match else None


def _plain(value: Any) -> str:
    if isinstance(value, list):
        value = " ".join(str(x) for x in value)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(value or ""))).strip()[:3000]


def _first(value: Any) -> str | None:
    if isinstance(value, list):
        return ", ".join(str(x) for x in value[:5]) or None
    return str(value)[:255] if value else None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolution(name: str) -> str | None:
    match = re.search(r"(?i)(2160|1080|720|480|360)p", name)
    return f"{match.group(1)}p" if match else None
