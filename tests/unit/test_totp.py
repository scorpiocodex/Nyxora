"""ServiceTOTP: codes for the 80-bit secrets services issue, which pyotp 2.12+ rejects."""

import base64
import hashlib
import hmac
import struct

import pyotp
import pytest

from nyxora.core.totp import ServiceTOTP

SECRET_80_BIT = "JBSWY3DPEHPK3PXP"  # 16 base32 characters, what many services issue
SECRET_160_BIT = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # RFC 6238's 20-byte test key


def _reference_code(secret_b32: str, unix_time: int, digits: int = 6) -> str:
    """RFC 4226/6238 written out, so the test does not rely on pyotp to check pyotp."""
    key = base64.b32decode(secret_b32)
    mac = hmac.new(key, struct.pack(">Q", unix_time // 30), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**digits).zfill(digits)


def test_accepts_an_80_bit_secret_and_matches_the_rfc_algorithm() -> None:
    for moment in (59, 1_111_111_109, 1_234_567_890, 2_000_000_000):
        assert ServiceTOTP(SECRET_80_BIT).at(moment) == _reference_code(SECRET_80_BIT, moment)


def test_matches_the_rfc_6238_test_vector() -> None:
    # RFC 6238 appendix B: SHA-1, T=59 gives 94287082 (8 digits), so 287082 with 6.
    assert ServiceTOTP(SECRET_160_BIT).at(59) == "287082"


def test_verify_and_provisioning_uri_work_for_short_secrets() -> None:
    totp = ServiceTOTP(SECRET_80_BIT)
    assert totp.verify(totp.at(1_700_000_000), for_time=1_700_000_000)
    assert totp.provisioning_uri(name="me", issuer_name="NYXORA").startswith("otpauth://totp/")


def test_secrets_nyxora_generates_itself_are_unaffected() -> None:
    secret = pyotp.random_base32()
    assert len(base64.b32decode(secret)) * 8 >= 160
    assert len(ServiceTOTP(secret).now()) == 6


def test_still_rejects_secrets_too_short_to_be_real() -> None:
    with pytest.raises(ValueError):
        ServiceTOTP("ABCDEF234567").now()  # 12 characters = 60 bits
