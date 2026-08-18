from collections.abc import Callable, Mapping
from typing import Any, TypeVar

from app.database.models import RepositoryDataError


Record = TypeVar("Record")


def _rows(response: Any, *, operation: str) -> list[Mapping[str, object]]:
    data = getattr(response, "data", None)

    if not isinstance(data, list):
        raise RepositoryDataError(
            f"{operation} retornou dados fora do formato esperado"
        )
    if not all(isinstance(row, Mapping) for row in data):
        raise RepositoryDataError(
            f"{operation} retornou linha fora do formato esperado"
        )

    return data


def create_one(
    response: Any,
    *,
    operation: str,
    parser: Callable[[Mapping[str, object]], Record],
) -> Record:
    rows = _rows(response, operation=operation)

    if len(rows) != 1:
        raise RepositoryDataError(
            f"{operation} deve retornar exatamente um registro"
        )

    return parser(rows[0])


def read_one_or_none(
    query: Any,
    *,
    operation: str,
    parser: Callable[[Mapping[str, object]], Record],
) -> Record | None:
    response = query.limit(2).execute()
    rows = _rows(response, operation=operation)

    if not rows:
        return None
    if len(rows) > 1:
        raise RepositoryDataError(
            f"{operation} retornou mais de um registro"
        )

    return parser(rows[0])
