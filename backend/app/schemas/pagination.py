"""
Einheitliche Pagination-Schemas fuer alle API-Endpunkte

Verwendung:
    from app.schemas.pagination import PaginationParams, PaginatedResponse

    @router.get("/items", response_model=PaginatedResponse[ItemSchema])
    async def list_items(
        pagination: PaginationParams = Depends(),
        db: AsyncSession = Depends(get_db),
    ):
        # pagination.page, pagination.page_size, pagination.offset verfuegbar
        ...
        return PaginatedResponse.create(items, total, pagination)
"""
from typing import Generic, TypeVar, List, Optional
from pydantic import BaseModel, Field
from fastapi import Query


T = TypeVar("T")


class PaginationParams:
    """
    Dependency fuer Pagination-Parameter.

    Einheitliche Parameter:
    - page: Seitennummer (1-basiert)
    - page_size: Elemente pro Seite (10-200)

    Properties:
    - offset: Berechnet aus page und page_size
    """

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Seitennummer (1-basiert)"),
        page_size: int = Query(50, ge=10, le=200, description="Elemente pro Seite"),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        """Berechnet Offset fuer SQL OFFSET"""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Alias fuer page_size (fuer SQL LIMIT)"""
        return self.page_size


class PaginationMeta(BaseModel):
    """Metadata fuer paginierte Responses"""
    page: int = Field(..., description="Aktuelle Seite")
    page_size: int = Field(..., description="Elemente pro Seite")
    total: int = Field(..., description="Gesamtzahl der Elemente")
    total_pages: int = Field(..., description="Gesamtzahl der Seiten")
    has_next: bool = Field(..., description="Gibt es eine naechste Seite?")
    has_prev: bool = Field(..., description="Gibt es eine vorherige Seite?")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generische paginierte Response.

    Verwendung:
        class ItemSchema(BaseModel):
            id: int
            name: str

        @router.get("/items", response_model=PaginatedResponse[ItemSchema])
        async def list_items(...):
            ...
    """
    items: List[T] = Field(..., description="Liste der Elemente")
    pagination: PaginationMeta = Field(..., description="Pagination-Metadaten")

    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        params: PaginationParams,
    ) -> "PaginatedResponse[T]":
        """
        Factory-Methode zum Erstellen einer paginierten Response.

        Args:
            items: Liste der Elemente fuer die aktuelle Seite
            total: Gesamtzahl aller Elemente
            params: PaginationParams Dependency
        """
        total_pages = (total + params.page_size - 1) // params.page_size if total > 0 else 0

        return cls(
            items=items,
            pagination=PaginationMeta(
                page=params.page,
                page_size=params.page_size,
                total=total,
                total_pages=total_pages,
                has_next=params.page < total_pages,
                has_prev=params.page > 1,
            ),
        )


# =============================================================================
# Hilfsfunktionen fuer Query-Builder
# =============================================================================

def apply_pagination(query, params: PaginationParams):
    """
    Wendet Pagination auf eine SQLAlchemy Query an.

    Verwendung:
        query = select(Model).where(...)
        query = apply_pagination(query, params)
    """
    return query.offset(params.offset).limit(params.limit)
