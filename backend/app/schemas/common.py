from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 25
    search: str | None = None
    sort_by: str | None = None
    sort_dir: str = "asc"
