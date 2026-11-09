from bot.services.license_verification import verify_archive_rights


def test_accepts_explicit_cc_by_4():
    ok, label, url = verify_archive_rights({"licenseurl": "https://creativecommons.org/licenses/by/4.0/"})
    assert ok and label == "CC BY 4.0" and url.endswith("by/4.0/")


def test_rejects_missing_license():
    assert verify_archive_rights({"title": "Unclear rights"}) == (False, None, None)


def test_rejects_non_allowlisted_license():
    assert verify_archive_rights({"licenseurl": "https://creativecommons.org/licenses/by-nc/4.0/"}) == (False, None, None)


def test_rejects_contradictory_rights_statement():
    assert verify_archive_rights({
        "licenseurl": "https://creativecommons.org/publicdomain/zero/1.0/",
        "rights": "All rights reserved",
    }) == (False, None, None)


def test_rejects_non_https_or_untrusted_host():
    assert verify_archive_rights({"licenseurl": "http://creativecommons.org/licenses/by/4.0/"}) == (False, None, None)
    assert verify_archive_rights({"licenseurl": "https://example.com/licenses/by/4.0/"}) == (False, None, None)


def test_rejects_unrecognized_path_suffix_and_lookalike_host():
    assert verify_archive_rights({"licenseurl": "https://creativecommons.org/licenses/by/4.0/extra"}) == (False, None, None)
    assert verify_archive_rights({"licenseurl": "https://creativecommons.org.evil.example/licenses/by/4.0/"}) == (False, None, None)
