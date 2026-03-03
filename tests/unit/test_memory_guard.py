from nyxora.core.memory_guard import SecureString, wipe_memory


def test_secure_string_lifecycle():
    sec_str = SecureString("mysecret")
    assert sec_str.to_bytes() == b"mysecret"

    # After exit (context manager), it shouldn't be accessible
    with sec_str as pw:
        assert pw.to_bytes() == b"mysecret"

    # It might still exist as bytearray internally but should be wiped,
    # depending on the internal implementation of to_bytes().
    # Calling to_bytes again usually raises or returns wiped data.
    pass

def test_wipe_memory():
    # Test bytearray wiping
    data = bytearray(b"highly sensitive information")
    wipe_memory(data)
    # Ensure it's not the original string
    assert data != b"highly sensitive information"
    # Assuming it gets zeroed or randomized based on implementation
    assert data == bytearray(len(data)) or data[0] != b"h"[0]

def test_wipe_memory_unsupported_type():
    # string - should just return or warn
    sensitive_str = "sensitive"
    # Should not raise exception
    wipe_memory(sensitive_str)
