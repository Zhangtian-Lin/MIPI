from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row


def psycopg_dsn(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


@contextmanager
def open_database(database_url: str) -> Iterator[Connection[dict[str, Any]]]:
    connection = psycopg.connect(psycopg_dsn(database_url), row_factory=dict_row)
    try:
        yield connection
    finally:
        connection.close()
