from uuid import UUID, uuid4


def new_id(prefix: str) -> str:
    """Create a stable public identifier without exposing database sequence values."""
    return f"{prefix}-{uuid4()}"


def parse_id(value: str, expected_prefix: str) -> UUID:
    prefix = f"{expected_prefix}-"
    if not value.startswith(prefix):
        raise ValueError(f"Expected identifier with prefix {expected_prefix}")
    return UUID(value.removeprefix(prefix))

