"""Conservative Internet Archive rights gate. Unknown or ambiguous rights are rejected."""
from urllib.parse import urlparse

_ALLOWED_LICENSES = {
    "creativecommons.org/publicdomain/zero/1.0/": "CC0 1.0",
    "creativecommons.org/publicdomain/mark/1.0/": "Public Domain Mark 1.0",
    "creativecommons.org/licenses/by/1.0/": "CC BY 1.0",
    "creativecommons.org/licenses/by/2.0/": "CC BY 2.0",
    "creativecommons.org/licenses/by/2.5/": "CC BY 2.5",
    "creativecommons.org/licenses/by/3.0/": "CC BY 3.0",
    "creativecommons.org/licenses/by/4.0/": "CC BY 4.0",
    "creativecommons.org/licenses/by-sa/1.0/": "CC BY-SA 1.0",
    "creativecommons.org/licenses/by-sa/2.0/": "CC BY-SA 2.0",
    "creativecommons.org/licenses/by-sa/2.5/": "CC BY-SA 2.5",
    "creativecommons.org/licenses/by-sa/3.0/": "CC BY-SA 3.0",
    "creativecommons.org/licenses/by-sa/4.0/": "CC BY-SA 4.0",
}


def verify_archive_rights(metadata: dict) -> tuple[bool, str | None, str | None]:
    """Return (allowed, human label, canonical license URL). Require explicit known license metadata."""
    raw = str(metadata.get("licenseurl") or metadata.get("license_url") or "").strip()
    if not raw:
        return False, None, None
    parsed = urlparse(raw)
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"creativecommons.org", "www.creativecommons.org"}:
        return False, None, None
    path = parsed.path.lstrip("/")
    canonical = f"creativecommons.org/{path}"
    label = _ALLOWED_LICENSES.get(canonical)
    if not label:
        return False, None, None
    rights = str(metadata.get("rights") or "").lower()
    if any(term in rights for term in ("all rights reserved", "no redistribution", "permission required")):
        return False, None, None
    return True, label, f"https://{canonical}"
