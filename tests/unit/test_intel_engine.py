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


def test_vault_health_score():
    import time
    from unittest.mock import MagicMock

    from nyxora.core.crypto_engine import CryptoEngine
    from nyxora.core.intel_engine import IntelEngine

    engine = CryptoEngine(argon2_memory=8192, argon2_time=1, argon2_parallelism=1)
    intel = IntelEngine(engine)

    # Mock entries
    now = int(time.time())
    e1 = MagicMock()
    e1.id = "id1"; e1.password = "X#9kLmP!qRsT2vWz"
    e1.updated_at = now; e1.totp_secret = "JBSWY3DP"

    e2 = MagicMock()
    e2.id = "id2"; e2.password = "correcthorsebatterystaple"
    e2.updated_at = now; e2.totp_secret = None

    e3 = MagicMock()
    e3.id = "id3"; e3.password = "abc"   # weak
    e3.updated_at = now - (200 * 86400)  # 200 days old
    e3.totp_secret = None

    score = intel.compute_health_score([e1, e2, e3])

    assert 0 <= score.total <= 100
    assert score.grade in ("A", "B", "C", "D", "F")
    assert score.total_entries == 3
    assert score.old_entries_count == 1      # e3 is old
    assert score.totp_enabled_count == 1     # e1 has TOTP
    assert score.strength_score >= 0
    assert score.age_score < 10              # penalised for e3


def test_vault_health_score_empty():
    from nyxora.core.crypto_engine import CryptoEngine
    from nyxora.core.intel_engine import IntelEngine
    engine = CryptoEngine(argon2_memory=8192, argon2_time=1, argon2_parallelism=1)
    intel = IntelEngine(engine)
    score = intel.compute_health_score([])
    assert score.total == 100
    assert score.grade == "A"
