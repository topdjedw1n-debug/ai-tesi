"""
Unit tests for JWT helper functions

These tests are FAST (< 1ms each) and should catch type conversion bugs immediately.
"""
import pytest

from app.core.exceptions import AuthenticationError
from app.utils.jwt_helpers import extract_user_id_from_payload


class TestExtractUserIDFromPayload:
    """Unit tests for extract_user_id_from_payload()"""

    def test_valid_string_sub_converts_to_int(self):
        """Test that string 'sub' claim is converted to int"""
        payload = {"sub": "2", "type": "access"}
        result = extract_user_id_from_payload(payload)

        assert result == 2
        assert isinstance(result, int), f"Expected int, got {type(result)}"

    def test_valid_large_string_sub_converts_to_int(self):
        """Test large user IDs"""
        payload = {"sub": "123456", "type": "access"}
        result = extract_user_id_from_payload(payload)

        assert result == 123456
        assert isinstance(result, int)

    def test_invalid_non_numeric_sub_raises_error(self):
        """Test that non-numeric 'sub' raises AuthenticationError"""
        payload = {"sub": "abc", "type": "access"}

        with pytest.raises(AuthenticationError) as exc_info:
            extract_user_id_from_payload(payload)

        assert "invalid user id" in str(exc_info.value).lower()

    def test_missing_sub_raises_error(self):
        """Test that missing 'sub' raises AuthenticationError"""
        payload = {"type": "access"}  # no 'sub'

        with pytest.raises(AuthenticationError) as exc_info:
            extract_user_id_from_payload(payload)

        assert "missing subject claim" in str(exc_info.value).lower()

    def test_empty_string_sub_raises_error(self):
        """Test that empty string 'sub' raises error"""
        payload = {"sub": "", "type": "access"}

        with pytest.raises(AuthenticationError):
            extract_user_id_from_payload(payload)

    def test_zero_sub_raises_error(self):
        """Test that zero user ID raises error (invalid ID)"""
        payload = {"sub": "0", "type": "access"}

        with pytest.raises(AuthenticationError) as exc_info:
            extract_user_id_from_payload(payload)

        assert "invalid user id" in str(exc_info.value).lower()

    def test_negative_sub_raises_error(self):
        """Test that negative user ID raises error"""
        payload = {"sub": "-1", "type": "access"}

        with pytest.raises(AuthenticationError):
            extract_user_id_from_payload(payload)

    def test_none_sub_raises_error(self):
        """Test that None 'sub' raises error"""
        payload = {"sub": None, "type": "access"}

        with pytest.raises(AuthenticationError):
            extract_user_id_from_payload(payload)

    def test_integer_sub_works(self):
        """Test that already-integer 'sub' still works (edge case)"""
        # This shouldn't happen in real JWT, but test defensive coding
        payload = {"sub": 2, "type": "access"}  # already int

        result = extract_user_id_from_payload(payload)
        assert result == 2
        assert isinstance(result, int)
