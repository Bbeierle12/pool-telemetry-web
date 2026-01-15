"""Unit tests for authentication functions."""
import pytest
from app.api.routes.auth import (
    hash_pin,
    verify_pin,
    _legacy_hash_pin,
    _is_bcrypt_hash,
    create_access_token,
)


class TestPinHashing:
    """Tests for PIN hashing functions."""

    def test_hash_pin_returns_bcrypt_format(self):
        """hash_pin should return a bcrypt hash starting with $2b$."""
        pin_hash = hash_pin("1234")
        assert pin_hash.startswith("$2b$")
        assert len(pin_hash) == 60  # Standard bcrypt hash length

    def test_hash_pin_produces_unique_hashes(self):
        """Same PIN should produce different hashes (random salt)."""
        hash1 = hash_pin("1234")
        hash2 = hash_pin("1234")
        assert hash1 != hash2  # Different salts

    def test_hash_pin_different_pins_different_hashes(self):
        """Different PINs should produce different hashes."""
        hash1 = hash_pin("1234")
        hash2 = hash_pin("5678")
        assert hash1 != hash2


class TestPinVerification:
    """Tests for PIN verification."""

    def test_verify_correct_pin(self):
        """Correct PIN should verify successfully."""
        pin = "1234"
        pin_hash = hash_pin(pin)
        is_valid, needs_upgrade = verify_pin(pin, pin_hash)
        assert is_valid is True
        assert needs_upgrade is False

    def test_verify_incorrect_pin(self):
        """Incorrect PIN should fail verification."""
        pin_hash = hash_pin("1234")
        is_valid, needs_upgrade = verify_pin("9999", pin_hash)
        assert is_valid is False
        assert needs_upgrade is False

    def test_verify_empty_pin(self):
        """Empty PIN should fail against non-empty hash."""
        pin_hash = hash_pin("1234")
        is_valid, needs_upgrade = verify_pin("", pin_hash)
        assert is_valid is False

    def test_verify_pin_case_sensitive(self):
        """PIN verification should be exact match."""
        pin_hash = hash_pin("abcd")
        is_valid, _ = verify_pin("ABCD", pin_hash)
        assert is_valid is False

    def test_verify_special_characters(self):
        """PINs with special characters should work."""
        pin = "12!@#$"
        pin_hash = hash_pin(pin)
        is_valid, _ = verify_pin(pin, pin_hash)
        assert is_valid is True


class TestLegacyHashMigration:
    """Tests for legacy SHA256 hash migration."""

    def test_legacy_hash_detection(self):
        """Legacy SHA256 hashes should be detected as non-bcrypt."""
        legacy_hash = _legacy_hash_pin("1234")
        assert _is_bcrypt_hash(legacy_hash) is False
        assert len(legacy_hash) == 64  # SHA256 hex length

    def test_bcrypt_hash_detection(self):
        """Bcrypt hashes should be detected correctly."""
        bcrypt_hash = hash_pin("1234")
        assert _is_bcrypt_hash(bcrypt_hash) is True

    def test_verify_legacy_hash_flags_upgrade(self):
        """Verifying legacy hash should flag for upgrade."""
        legacy_hash = _legacy_hash_pin("5678")
        is_valid, needs_upgrade = verify_pin("5678", legacy_hash)
        assert is_valid is True
        assert needs_upgrade is True

    def test_verify_legacy_hash_wrong_pin(self):
        """Wrong PIN on legacy hash should not flag upgrade."""
        legacy_hash = _legacy_hash_pin("5678")
        is_valid, needs_upgrade = verify_pin("9999", legacy_hash)
        assert is_valid is False
        assert needs_upgrade is False

    def test_legacy_hash_deterministic(self):
        """Legacy hash should be deterministic (same input = same output)."""
        hash1 = _legacy_hash_pin("1234")
        hash2 = _legacy_hash_pin("1234")
        assert hash1 == hash2


class TestJwtTokenCreation:
    """Tests for JWT token creation."""

    def test_create_access_token_returns_string(self):
        """create_access_token should return a JWT string."""
        token = create_access_token("test-profile-id")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_has_three_parts(self):
        """JWT should have header.payload.signature format."""
        token = create_access_token("test-profile-id")
        parts = token.split(".")
        assert len(parts) == 3

    def test_different_profile_ids_different_tokens(self):
        """Different profile IDs should produce different tokens."""
        token1 = create_access_token("profile-1")
        token2 = create_access_token("profile-2")
        assert token1 != token2
