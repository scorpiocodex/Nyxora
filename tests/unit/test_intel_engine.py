from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import RequestException

from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.intel_engine import IntelEngine
from nyxora.utils.exceptions import NyxoraError


@pytest.fixture
def intel():
    crypto = CryptoEngine()
    return IntelEngine(crypto)

def test_score_entropy(intel):
    score = intel.score_entropy("password")
    assert score > 0
    assert score < intel.score_entropy("Tr0ub4dor&3!")

def test_classify_strength(intel):
    assert intel.classify_strength(10) == "Weak"
    assert intel.classify_strength(45) == "Fair"
    assert intel.classify_strength(70) == "Strong"
    assert intel.classify_strength(90) == "Excellent"

def test_scan_patterns(intel):
    patterns = intel.scan_patterns("12345password")
    assert "keyboard_walk" in patterns
    assert "common_word_base" in patterns

@patch("nyxora.core.intel_engine.requests.get")
@patch("nyxora.core.intel_engine.time.sleep")
def test_check_breach_hibp_success(mock_sleep, mock_get, intel):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "SUFFIX:123\nANOTHER:456"
    mock_get.return_value = mock_resp

    with patch.object(intel._crypto, "hash_for_hibp", return_value=("PREFI", "SUFFIX")):
        is_breached, count = intel.check_breach_hibp("hunter2")
        assert is_breached is True
        assert count == 123

@patch("nyxora.core.intel_engine.requests.get")
@patch("nyxora.core.intel_engine.time.sleep")
def test_check_breach_hibp_not_found(mock_sleep, mock_get, intel):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "NOTSUFFIX:123"
    mock_get.return_value = mock_resp

    with patch.object(intel._crypto, "hash_for_hibp", return_value=("PREFI", "SUFFIX")):
        is_breached, count = intel.check_breach_hibp("strongpw123!")
        assert is_breached is False
        assert count == 0

@patch("nyxora.core.intel_engine.requests.get")
@patch("nyxora.core.intel_engine.time.sleep")
def test_check_breach_hibp_retry_429(mock_sleep, mock_get, intel):
    # Setup response sequence: 429, 429, 200
    def side_effect(*args, **kwargs):
        resp = MagicMock()
        if mock_get.call_count < 3:
            resp.status_code = 429
        else:
            resp.status_code = 200
            resp.text = "NOTMATCH:1"
        return resp

    mock_get.side_effect = side_effect

    with patch.object(intel._crypto, "hash_for_hibp", return_value=("PREFI", "SUFFIX")):
        is_breached, count = intel.check_breach_hibp("testpw")
        assert mock_get.call_count == 3
        # Should have slept 2 times due to retry
        assert mock_sleep.call_count == 2
        assert is_breached is False

@patch("nyxora.core.intel_engine.requests.get")
@patch("nyxora.core.intel_engine.time.sleep")
def test_check_breach_hibp_retry_failure(mock_sleep, mock_get, intel):
    # Setup response sequence: 429 constantly
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_get.return_value = mock_resp

    with patch.object(intel._crypto, "hash_for_hibp", return_value=("PREFI", "SUFFIX")):
        with pytest.raises(NyxoraError, match="API rate limit exceeded"):
            intel.check_breach_hibp("testpw")
        assert mock_get.call_count == 3

@patch("nyxora.core.intel_engine.requests.get")
@patch("nyxora.core.intel_engine.time.sleep")
def test_check_breach_hibp_network_error(mock_sleep, mock_get, intel):
    # Setup response sequence: RequestException, 200
    def side_effect(*args, **kwargs):
        if mock_get.call_count == 1:
            raise RequestException("Network error")
        resp = MagicMock()
        resp.status_code = 200
        resp.text = ""
        return resp

    mock_get.side_effect = side_effect

    with patch.object(intel._crypto, "hash_for_hibp", return_value=("PREFI", "SUFFIX")):
        intel.check_breach_hibp("testpw")
        assert mock_get.call_count == 2
        assert mock_sleep.call_count == 1
