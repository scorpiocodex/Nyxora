from unittest.mock import patch

from nyxora import __version__
from nyxora.core.update_engine import (
    background_check,
    get_checksums_asset,
    get_wheel_asset,
    is_newer,
    should_check_now,
    verify_checksum,
)


def test_is_newer_true():
    # A version higher than current should be newer
    major, minor, patch_ = (int(x) for x in __version__.split("."))
    future = f"v{major}.{minor}.{patch_ + 1}"
    release = {"tag_name": future}
    assert is_newer(release) is True


def test_is_newer_false_same():
    release = {"tag_name": f"v{__version__}"}
    assert is_newer(release) is False


def test_is_newer_false_older():
    release = {"tag_name": "v0.0.1"}
    assert is_newer(release) is False


def test_is_newer_bad_tag():
    release = {"tag_name": "not-a-version"}
    assert is_newer(release) is False


def test_get_wheel_asset_found():
    release = {"assets": [
        {"name": "nyxora-2.6.1-py3-none-any.whl",
         "browser_download_url": "https://example.com/nyxora.whl"},
        {"name": "nyxora-2.6.1.tar.gz",
         "browser_download_url": "https://example.com/nyxora.tar.gz"},
    ]}
    asset = get_wheel_asset(release)
    assert asset is not None
    assert asset["name"].endswith(".whl")


def test_get_wheel_asset_not_found():
    release = {"assets": [{"name": "README.md"}]}
    assert get_wheel_asset(release) is None


def test_get_checksums_asset():
    release = {"assets": [
        {"name": "sha256sums.txt", "browser_download_url": "https://x.com/s"},
        {"name": "nyxora.whl", "browser_download_url": "https://x.com/w"},
    ]}
    asset = get_checksums_asset(release)
    assert asset is not None
    assert asset["name"] == "sha256sums.txt"


def test_verify_checksum_match(tmp_path):
    f = tmp_path / "nyxora-2.6.1-py3-none-any.whl"
    f.write_bytes(b"fake wheel content")
    import hashlib
    h = hashlib.sha256(b"fake wheel content").hexdigest()
    checksums_text = f"{h}  nyxora-2.6.1-py3-none-any.whl\n"
    assert verify_checksum(f, checksums_text) is True


def test_verify_checksum_mismatch(tmp_path):
    f = tmp_path / "nyxora-2.6.1-py3-none-any.whl"
    f.write_bytes(b"fake wheel content")
    checksums_text = "aabbccddeeff0011  nyxora-2.6.1-py3-none-any.whl\n"
    assert verify_checksum(f, checksums_text) is False


def test_verify_checksum_not_in_file(tmp_path):
    f = tmp_path / "nyxora-2.6.1-py3-none-any.whl"
    f.write_bytes(b"content")
    assert verify_checksum(f, "abc123  other_file.whl\n") is False


def test_should_check_now_first_time(tmp_path):
    # When no state file exists, should check now
    with patch("nyxora.core.update_engine.STATE_FILE",
               tmp_path / "update_state.json"):
        assert should_check_now(interval_hours=24) is True


def test_should_check_now_recent(tmp_path):
    import json
    import time
    state_file = tmp_path / "update_state.json"
    state_file.write_text(
        json.dumps({"last_check": int(time.time())}),
        encoding="utf-8"
    )
    with patch("nyxora.core.update_engine.STATE_FILE", state_file):
        assert should_check_now(interval_hours=24) is False


def test_background_check_no_update(tmp_path):
    with patch("nyxora.core.update_engine.STATE_FILE",
               tmp_path / "s.json"), \
         patch("nyxora.core.update_engine.fetch_latest_release",
               return_value={"tag_name": f"v{__version__}"}):
        result = background_check("stable")
    assert result is None


def test_background_check_update_available(tmp_path):
    major, minor, patch_ = (int(x) for x in __version__.split("."))
    future_tag = f"v{major}.{minor}.{patch_ + 1}"
    with patch("nyxora.core.update_engine.STATE_FILE",
               tmp_path / "s.json"), \
         patch("nyxora.core.update_engine.fetch_latest_release",
               return_value={"tag_name": future_tag}):
        result = background_check("stable")
    assert result is not None
    assert future_tag in result


def test_background_check_network_error(tmp_path):
    with patch("nyxora.core.update_engine.STATE_FILE",
               tmp_path / "s.json"), \
         patch("nyxora.core.update_engine.fetch_latest_release",
               return_value=None):
        result = background_check("stable")
    assert result is None
