from __future__ import annotations

from typing import Any


def normalize_search_item(item: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a MovieBox v2 search record to the bot's safe metadata shape."""
    try:
        subject_type = int(item.get("subjectType"))
    except (TypeError, ValueError):
        return None
    if subject_type not in {1, 2}:
        return None

    subject_id = str(item.get("subjectId") or "").strip()
    detail_path = str(item.get("detailPath") or "").strip()
    title = str(item.get("title") or "").strip()
    if not subject_id or not detail_path or not title:
        return None

    release_date = str(item.get("releaseDate") or "")
    genre = item.get("genre") or []
    if isinstance(genre, str):
        genre = [part.strip() for part in genre.split(",") if part.strip()]
    elif not isinstance(genre, list):
        genre = []

    return {
        "subject_id": subject_id,
        "detail_path": detail_path,
        "title": title,
        "kind": "Movie" if subject_type == 1 else "TV series",
        "year": release_date[:4] if len(release_date) >= 4 else "",
        "rating": item.get("imdbRatingValue"),
        "genres": [str(value) for value in genre[:8]],
        "description": str(item.get("description") or ""),
        "country": str(item.get("countryName") or ""),
    }


def normalize_details(payload: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """Keep only descriptive metadata; never expose stream or download URLs."""
    subject = payload.get("subject") or {}
    metadata = payload.get("metadata") or {}
    resource = payload.get("resource") or {}

    genres = subject.get("genre") or fallback.get("genres") or []
    if isinstance(genres, str):
        genres = [part.strip() for part in genres.split(",") if part.strip()]
    seasons = resource.get("seasons") or []

    return {
        "title": str(metadata.get("title") or subject.get("title") or fallback["title"]),
        "description": str(metadata.get("description") or subject.get("description") or fallback.get("description") or ""),
        "year": str(subject.get("releaseDate") or fallback.get("year") or "")[:4],
        "rating": subject.get("imdbRatingValue", fallback.get("rating")),
        "genres": [str(value) for value in genres[:8]],
        "country": str(subject.get("countryName") or fallback.get("country") or ""),
        "duration": subject.get("duration"),
        "seasons": [
            {
                "number": season.get("se"),
                "episodes": season.get("maxEp"),
                "resolutions": [
                    resolution.get("resolution")
                    for resolution in (season.get("resolutions") or [])
                    if isinstance(resolution, dict)
                ],
            }
            for season in seasons[:30]
            if isinstance(season, dict)
        ],
    }


class MovieBoxCatalog:
    """Async metadata/search adapter for the exact hoby-qode MovieBox API."""

    async def search(self, query: str, page: int = 1, per_page: int = 8) -> dict[str, Any]:
        if len(query.strip()) < 2:
            return {"items": [], "has_next": False}

        from moviebox_api.v1.constants import SubjectType
        from moviebox_api.v2 import Search, Session

        session = Session(timeout=20)
        try:
            response = await Search(
                session=session,
                query=query.strip(),
                subject_type=SubjectType.ALL,
                page=max(1, page),
                per_page=max(1, min(per_page, 20)),
            ).get_content()
            items = [
                normalized
                for raw in response.get("items", [])
                if isinstance(raw, dict)
                if (normalized := normalize_search_item(raw)) is not None
            ]
            pager = response.get("pager") or {}
            return {"items": items, "has_next": bool(pager.get("hasMore"))}
        finally:
            await session._client.aclose()

    async def details(self, detail_path: str, fallback: dict[str, Any]) -> dict[str, Any]:
        from moviebox_api.v2 import ItemDetails, Session

        session = Session(timeout=20)
        try:
            payload = await ItemDetails(session=session).get_content(detail_path)
            if not isinstance(payload, dict):
                raise ValueError("MovieBox returned an invalid details response")
            return normalize_details(payload, fallback)
        finally:
            await session._client.aclose()
