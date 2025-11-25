"""JWT helper utilities"""

from app.core.exceptions import AuthenticationError


def extract_user_id_from_payload(payload: dict) -> int:
    """
    Extract and validate user ID from JWT payload.

    JWT standard returns all claims as strings, but database expects INTEGER.
    This function converts the 'sub' claim from string to int and validates it.

    Args:
        payload: Decoded JWT payload dictionary

    Returns:
        int: Validated user ID as integer

    Raises:
        AuthenticationError: If user ID is missing or invalid
    """
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token: missing subject claim")

    try:
        user_id = int(user_id)
        if user_id <= 0:
            raise AuthenticationError("Invalid token: invalid user ID")
        return user_id
    except (ValueError, TypeError) as e:
        raise AuthenticationError("Invalid token: invalid user ID") from e
