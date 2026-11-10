from __future__ import annotations

import asyncio
import re
from urllib.parse import quote, unquote

import aiohttp

from bot.config import settings
from bot.services.archive_api import ArchiveAPI
from bot.services.license_verification import verify_archive_rights

LOC_SEARCH = "https://www.loc.gov/film-and-videos/"
LOC_ITEM = "https://www.loc.gov/item/{identifier}/"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
VIDEO_EXTENSIONS = (".mp4", ".webm", ".ogv", ".m4v", ".mov")


def _text(value) -> str:
    if isinstance(value, list):
        value = " ".join(str(x) for x in value)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(value or ""))).strip()[:3000]


def _year(value) -> int | None:
    match = re.search(r"\b(?:18|19|20)\d{2}\b", str(value or ""))
    return int(match.group()) if match else None


def _size(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class MultiSourceCatalog:
    """Unified catalog; external sources require an explicit allowlisted CC/PD license URL."""

    def __init__(self, session: aiohttp.ClientSession):
        self.http = session
        self.archive = ArchiveAPI(session)
        self._records: dict[str, dict] = {}

    async def _json(self, url: str, params: dict | None = None) -> dict:
        timeout = aiohttp.ClientTimeout(total=settings.request_timeout_seconds)
        async with self.http.get(url, params=params, timeout=timeout) as response:
            response.raise_for_status()
            return await response.json(content_type=None)

    async def search(self, query: str, page: int = 0) -> list[dict]:
        query = " ".join(str(query).split())[:100]
        if len(query) < 2:
            return []
        results = await asyncio.gather(
            self.archive.search(query, page),
            self._search_loc(query, page),
            self._search_commons(query, page),
            return_exceptions=True,
        )
        merged: list[dict] = []
        for result in results:
            if isinstance(result, list):
                merged.extend(result)
        seen: set[str] = set()
        unique = []
        for item in merged:
            identifier = str(item.get("identifier") or "")
            if identifier and identifier not in seen:
                seen.add(identifier)
                unique.append(item)
        unique.sort(key=lambda item: (item.get("year") is None, item.get("title", "").casefold()))
        return unique[:max(settings.archive_page_size, 10)]

    async def details(self, identifier: str) -> dict | None:
        if identifier.startswith("loc:"):
            return await self._loc_details(identifier[4:])
        if identifier.startswith("commons:"):
            return await self._commons_details(identifier[8:])
        return await self.archive.details(identifier)

    async def _search_loc(self, query: str, page: int) -> list[dict]:
        payload = await self._json(LOC_SEARCH, {"q": query, "fo": "json", "c": 20, "sp": page + 1})
        output = []
        for doc in payload.get("results", []):
            identifier = str(doc.get("id") or "").rstrip("/").split("/")[-1]
            title = _text(doc.get("title"))
            if not identifier or not title:
                continue
            ok, label, canonical = verify_archive_rights({"licenseurl": doc.get("rights") or doc.get("rights_url")})
            if not ok:
                continue
            record = {
                "identifier": f"loc:{identifier}", "title": title,
                "year": _year(doc.get("date") or doc.get("created_published")),
                "description": _text(doc.get("description")), "license": label,
                "license_url": canonical, "source_url": doc.get("url") or LOC_ITEM.format(identifier=quote(identifier)),
            }
            self._records[record["identifier"]] = record
            output.append(record)
        return output

    async def _loc_details(self, identifier: str) -> dict | None:
        payload = await self._json(LOC_ITEM.format(identifier=quote(identifier)), {"fo": "json"})
        item = payload.get("item") or payload
        title = _text(item.get("title"))
        ok, label, canonical = verify_archive_rights({"licenseurl": item.get("rights") or item.get("rights_url")})
        if not title or not ok:
            return None
        files = []
        for resource in item.get("resources", []) or []:
            url = str(resource.get("url") or "")
            name = unquote(url.split("?")[0].rsplit("/", 1)[-1])
            mime = str(resource.get("mimetype") or resource.get("mime_type") or "").lower()
            from urllib.parse import urlparse
            host = (urlparse(url).hostname or "").lower()
            trusted_host = host == "loc.gov" or host.endswith(".loc.gov")
            if not trusted_host or urlparse(url).scheme != "https":
                continue
            if not (mime.startswith("video/") or name.lower().endswith(VIDEO_EXTENSIONS)):
                continue
            files.append({
                "filename": name[:500] or f"{identifier}.mp4",
                "format": (name.rsplit(".", 1)[-1] if "." in name else "video").upper()[:40],
                "resolution": None, "file_size": _size(resource.get("filesize") or resource.get("size")),
                "download_url": url, "codec": None,
            })
        if not files:
            return None
        return {
            "identifier": f"loc:{identifier}", "title": title,
            "description": _text(item.get("description")),
            "year": _year(item.get("date") or item.get("created_published")),
            "genre": None, "language": None, "poster_url": None,
            "license": label, "license_url": canonical,
            "source_url": item.get("url") or LOC_ITEM.format(identifier=quote(identifier)),
            "files": files, "raw": {"source": "Library of Congress"},
        }

    async def _search_commons(self, query: str, page: int) -> list[dict]:
        payload = await self._json(COMMONS_API, {
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": f'filetype:video "{query}"', "gsrnamespace": 6,
            "gsrlimit": 20, "gsroffset": page * 20,
            "prop": "imageinfo", "iiprop": "url|size|extmetadata",
        })
        pages = (payload.get("query") or {}).get("pages") or {}
        output = []
        for page_data in pages.values():
            title = _text(page_data.get("title"))
            info = (page_data.get("imageinfo") or [{}])[0]
            ext = info.get("extmetadata") or {}
            ok, label, canonical = verify_archive_rights({
                "licenseurl": (ext.get("LicenseUrl") or {}).get("value")
            })
            media_url = str(info.get("url") or "")
            from urllib.parse import urlparse
            host = (urlparse(media_url).hostname or "").lower()
            if not ok or host != "upload.wikimedia.org" or urlparse(media_url).scheme != "https":
                continue
            if not media_url.lower().split("?")[0].endswith(VIDEO_EXTENSIONS):
                continue
            identifier = str(page_data.get("pageid") or "")
            if not identifier:
                continue
            year = _year((ext.get("DateTimeOriginal") or {}).get("value") or (ext.get("DateTime") or {}).get("value"))
            record = {
                "identifier": f"commons:{identifier}", "title": title, "year": year,
                "description": _text((ext.get("ImageDescription") or {}).get("value")),
                "license": label, "license_url": canonical,
                "source_url": info.get("descriptionurl") or "https://commons.wikimedia.org/",
            }
            self._records[record["identifier"]] = {
                **record, "media_url": media_url, "filename": title.rsplit(":", 1)[-1],
                "size": _size(info.get("size")),
            }
            output.append(record)
        return output

    async def _commons_details(self, page_id: str) -> dict | None:
        cached = self._records.get(f"commons:{page_id}")
        if not cached:
            return None
        ok, label, canonical = verify_archive_rights({"licenseurl": cached.get("license_url")})
        if not ok:
            return None
        filename = cached.get("filename") or f"{page_id}.mp4"
        return {
            "identifier": f"commons:{page_id}", "title": cached["title"],
            "description": cached.get("description"), "year": cached.get("year"),
            "genre": None, "language": None, "poster_url": None,
            "license": label, "license_url": canonical, "source_url": cached["source_url"],
            "files": [{
                "filename": filename[:500], "format": filename.rsplit(".", 1)[-1].upper()[:40],
                "resolution": None, "file_size": cached.get("size"),
                "download_url": cached["media_url"], "codec": None,
            }],
            "raw": {"source": "Wikimedia Commons"},
        }
