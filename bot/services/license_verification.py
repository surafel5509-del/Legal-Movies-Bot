"""Conservative rights gate shared by Internet Archive, LOC and Commons.

Only explicit CC0, Public Domain Mark, CC BY and CC BY-SA license URLs pass.
Statements such as "no known restrictions" are not treated as redistribution licenses.
"""
from urllib.parse import urlparse

_ALLOWED_LICENSES = {
    "creativecommons.org/publicdomain/zero/1.0/": "CC0 1.0",
    "creativecommons.org/publicdomain/mark/1.0/": "Public Domain Mark 1.0",
    **{
        f"creativecommons.org/licenses/{family}/{version}/": f"{family.upper()} {version}"
        for family in ("by", "by-sa")
        for version in ("1.0", "2.0", "2.5", "3.0", "4.0")
    },
}


def verify_archive_rights(metadata: dict) -> tuple[bool, str | None, str | None]:
    """Return (allowed, human label, canonical HTTPS license URL)."""
    raw = str(metadata.get("licenseurl") or metadata.get("license_url") or "").strip()
    if not raw:
        return False, None, None
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"https", "http"} or host not in {"creativecommons.org", "www.creativecommons.org"}:
        return False, None, None
    canonical = f"creativecommons.org/{parsed.path.lstrip('/')}"
    label = _ALLOWED_LICENSES.get(canonical)
    if not label:
        return False, None, None
    rights = str(metadata.get("rights") or "").lower()
    if any(term in rights for term in ("all rights reserved", "no redistribution", "permission required")):
        return False, None, None
    return True, label, f"https://{canonical}"
