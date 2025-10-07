import secrets


def generate_secret_key(length: int = 32):
    """Generate a secure random secret key."""
    return secrets.token_hex(length)


if __name__ == "__main__":
    key = generate_secret_key()
    print(f"Generated SECRET_KEY: {key}")
    print("\nCopy this to your .env file: SECRET_KEY=your-generated-key-here")
