"""TOTP codes for the secrets real services hand out.

pyotp 2.11 started rejecting any secret that decodes to fewer than 112 bits. Many
services still issue 80-bit secrets (16 base32 characters, the Google Authenticator
default), and a password manager has to produce codes for the secret the user was
given, not the one we would have chosen. pyotp documents ``min_secret_length_bits``
as the override point, so this subclass lowers it to 80 bits and everything else
behaves exactly like ``pyotp.TOTP``.

Older pyotp releases ignore the attribute, so this works across the supported range.
Secrets Nyxora generates itself (``pyotp.random_base32()``) are 160 bits and are
unaffected.
"""

from __future__ import annotations

from typing import ClassVar

import pyotp


class ServiceTOTP(pyotp.TOTP):
    """``pyotp.TOTP`` that accepts the 80-bit secrets services commonly issue."""

    min_secret_length_bits: ClassVar[int] = 80
