#!/usr/bin/env python3
"""
Generate secure secret keys for TesiGo application.

This script generates cryptographically secure random strings suitable for:
- SECRET_KEY: Application secret key
- JWT_SECRET: JWT signing secret key

Usage:
    python scripts/generate_secrets.py
"""

import secrets
import string


def generate_secret_key(length: int = 64) -> str:
    """
    Generate a cryptographically secure random string.
    
    Args:
        length: Desired length of the secret key (default: 64)
    
    Returns:
        A secure random string
    """
    # Use URL-safe base64 characters for better compatibility
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main():
    """Generate and display secret keys with instructions."""
    print("=" * 80)
    print("TesiGo Secret Key Generator")
    print("=" * 80)
    print()
    
    # Generate SECRET_KEY (32+ characters)
    secret_key = generate_secret_key(length=64)
    print("SECRET_KEY (64 chars):")
    print(secret_key)
    print()
    
    # Generate JWT_SECRET (32+ characters, different from SECRET_KEY)
    jwt_secret = generate_secret_key(length=64)
    # Ensure JWT_SECRET is different from SECRET_KEY
    while jwt_secret == secret_key:
        jwt_secret = generate_secret_key(length=64)
    
    print("JWT_SECRET (64 chars):")
    print(jwt_secret)
    print()
    
    print("=" * 80)
    print("Instructions:")
    print("=" * 80)
    print()
    print("1. Copy the above values to your .env file:")
    print()
    print("   SECRET_KEY=" + secret_key)
    print("   JWT_SECRET=" + jwt_secret)
    print()
    print("2. For production, also set:")
    print("   JWT_ISS=tesigo.com")
    print("   JWT_AUD=tesigo-api")
    print()
    print("3. IMPORTANT:")
    print("   - Never commit these values to version control")
    print("   - Keep them secure and rotate periodically")
    print("   - Use different values for each environment")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()

