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

    async def search(self, query: str, page: int = 0) -> list[dict]:
        query = re.sub(r"[^\w\s'-]", " ", query, flags=re.UNICODE).strip()[:100]
        if not query:
            return []
        key = (query.casefold(), page)
        async with self._lock:
            cached = self._cache.get(key)
            if cached and cached[0] > asyncio.get_running_loop().time():
                return cached[1]
        escaped = query.replace('"', '')
        params = {
            "q": f'mediatype:movies AND (title:"{escaped}" OR description:"{escaped}")',
            "fl[]": ["identifier", "title", "year", "description", "licenseurl", "rights", "publicdate"],
            "sort[]": "downloads desc",
            "rows": str(settings.archive_page_size),
            "page": str(page + 1),
            "output": "json",
        }
        payload = await self._json(ADVANCED_URL, params=params)
        docs = payload.get("response", {}).get("docs", [])
        unique_docs: list[dict] = []
        seen: set[str] = set()
        for doc in docs:
            identifier = str(doc.get("identifier", "")).strip()
            if identifier and identifier not in seen:
                seen.add(identifier)
                unique_docs.append(doc)

        # The Advanced Search index can omit licenseurl even when the canonical
        # item metadata contains it. Re-check only those candidates against the
        # item's metadata API; never relax the rights allowlist.
        semaphore = asyncio.Semaphore(5)

        async def verified_result(doc: dict) -> dict | None:
            identifier = str(doc["identifier"])
            rights_doc = doc
            if not doc.get("licenseurl") and not doc.get("license_url"):
                async with semaphore:
                    try:
                        metadata_payload = await self._json(
                            DETAIL_URL.format(identifier=quote(identifier, safe=""))
                        )
                    except (aiohttp.ClientError, asyncio.TimeoutError):
                        return None
                rights_doc = metadata_payload.get("metadata", {})
            rights_ok, license_label, license_url = verify_archive_rights(rights_doc)
            if not rights_ok:
                return None
            metadata = rights_doc if rights_doc is not doc else {}
            return {
                "identifier": identifier,
                "title": str(doc.get("title") or metadata.get("title") or identifier)[:500],
                "year": _year(doc.get("year") or metadata.get("year")),
                "description": _plain(doc.get("description") or metadata.get("description")),
                "license": license_label,
                "license_url": license_url,
                "source_url": f"https://archive.org/details/{quote(identifier)}",
            }

        verified = await asyncio.gather(*(verified_result(doc) for doc in unique_docs))
        results = [item for item in verified if item is not None]
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
