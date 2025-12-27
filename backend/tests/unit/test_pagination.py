"""
Tests fuer das einheitliche Pagination-Modul
"""
import pytest
from unittest.mock import MagicMock
from pydantic import BaseModel

from app.schemas.pagination import (
    PaginationParams,
    PaginationMeta,
    PaginatedResponse,
    apply_pagination,
)


# =============================================================================
# Beispiel-Schema fuer generische Response Tests
# =============================================================================

class SampleItem(BaseModel):
    """Beispiel-Schema fuer Tests (nicht 'Test' prefix um pytest-Warnung zu vermeiden)"""
    id: int
    name: str


# =============================================================================
# Tests fuer PaginationParams
# =============================================================================

class TestPaginationParams:
    """Tests fuer die PaginationParams Dependency"""

    def test_default_values(self):
        """Test der Standard-Werte (explizit uebergeben, da Query-Defaults nur bei FastAPI-Injection)"""
        params = PaginationParams(page=1, page_size=50)
        assert params.page == 1
        assert params.page_size == 50

    def test_custom_values(self):
        """Test mit eigenen Werten"""
        params = PaginationParams(page=3, page_size=25)
        assert params.page == 3
        assert params.page_size == 25

    def test_offset_calculation_page_1(self):
        """Test Offset-Berechnung fuer Seite 1"""
        params = PaginationParams(page=1, page_size=50)
        assert params.offset == 0

    def test_offset_calculation_page_2(self):
        """Test Offset-Berechnung fuer Seite 2"""
        params = PaginationParams(page=2, page_size=50)
        assert params.offset == 50

    def test_offset_calculation_page_10(self):
        """Test Offset-Berechnung fuer Seite 10"""
        params = PaginationParams(page=10, page_size=25)
        assert params.offset == 225  # (10-1) * 25

    def test_limit_property(self):
        """Test dass limit == page_size"""
        params = PaginationParams(page_size=100)
        assert params.limit == 100


# =============================================================================
# Tests fuer PaginationMeta
# =============================================================================

class TestPaginationMeta:
    """Tests fuer PaginationMeta Schema"""

    def test_pagination_meta_creation(self):
        """Test der Meta-Erstellung"""
        meta = PaginationMeta(
            page=2,
            page_size=50,
            total=150,
            total_pages=3,
            has_next=True,
            has_prev=True,
        )
        assert meta.page == 2
        assert meta.total == 150
        assert meta.has_next is True
        assert meta.has_prev is True


# =============================================================================
# Tests fuer PaginatedResponse
# =============================================================================

class TestPaginatedResponse:
    """Tests fuer die generische PaginatedResponse"""

    def test_create_empty_response(self):
        """Test mit leerer Liste"""
        params = PaginationParams(page=1, page_size=50)
        response = PaginatedResponse[SampleItem].create([], 0, params)

        assert response.items == []
        assert response.pagination.total == 0
        assert response.pagination.total_pages == 0
        assert response.pagination.has_next is False
        assert response.pagination.has_prev is False

    def test_create_with_items(self):
        """Test mit Elementen"""
        items = [
            SampleItem(id=1, name="Item 1"),
            SampleItem(id=2, name="Item 2"),
        ]
        params = PaginationParams(page=1, page_size=50)
        response = PaginatedResponse[SampleItem].create(items, 2, params)

        assert len(response.items) == 2
        assert response.items[0].name == "Item 1"
        assert response.pagination.total == 2
        assert response.pagination.total_pages == 1

    def test_total_pages_calculation_exact(self):
        """Test total_pages wenn total durch page_size teilbar"""
        params = PaginationParams(page=1, page_size=50)
        response = PaginatedResponse[SampleItem].create([], 100, params)
        assert response.pagination.total_pages == 2

    def test_total_pages_calculation_remainder(self):
        """Test total_pages mit Rest"""
        params = PaginationParams(page=1, page_size=50)
        response = PaginatedResponse[SampleItem].create([], 75, params)
        assert response.pagination.total_pages == 2  # 75/50 = 1.5 -> 2

    def test_total_pages_calculation_small(self):
        """Test total_pages wenn weniger als page_size"""
        params = PaginationParams(page=1, page_size=50)
        response = PaginatedResponse[SampleItem].create([], 30, params)
        assert response.pagination.total_pages == 1

    def test_has_next_first_page(self):
        """Test has_next auf erster Seite mit mehr Seiten"""
        params = PaginationParams(page=1, page_size=50)
        response = PaginatedResponse[SampleItem].create([], 100, params)
        assert response.pagination.has_next is True

    def test_has_next_last_page(self):
        """Test has_next auf letzter Seite"""
        params = PaginationParams(page=2, page_size=50)
        response = PaginatedResponse[SampleItem].create([], 100, params)
        assert response.pagination.has_next is False

    def test_has_prev_first_page(self):
        """Test has_prev auf erster Seite"""
        params = PaginationParams(page=1, page_size=50)
        response = PaginatedResponse[SampleItem].create([], 100, params)
        assert response.pagination.has_prev is False

    def test_has_prev_second_page(self):
        """Test has_prev auf zweiter Seite"""
        params = PaginationParams(page=2, page_size=50)
        response = PaginatedResponse[SampleItem].create([], 100, params)
        assert response.pagination.has_prev is True


# =============================================================================
# Tests fuer apply_pagination Hilfsfunktion
# =============================================================================

class TestApplyPagination:
    """Tests fuer die apply_pagination Hilfsfunktion"""

    def test_apply_pagination_calls_offset_and_limit(self):
        """Test dass offset und limit aufgerufen werden"""
        mock_query = MagicMock()
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query

        params = PaginationParams(page=3, page_size=25)
        result = apply_pagination(mock_query, params)

        mock_query.offset.assert_called_once_with(50)  # (3-1) * 25
        mock_query.limit.assert_called_once_with(25)
        assert result == mock_query


# =============================================================================
# Edge Cases
# =============================================================================

class TestPaginationEdgeCases:
    """Tests fuer Grenzfaelle"""

    def test_large_page_number(self):
        """Test mit grosser Seitenzahl"""
        params = PaginationParams(page=1000, page_size=50)
        response = PaginatedResponse[SampleItem].create([], 100, params)

        # Sollte keine Fehler werfen
        assert response.pagination.has_next is False
        assert response.pagination.has_prev is True

    def test_single_item_total(self):
        """Test mit genau einem Element"""
        params = PaginationParams(page=1, page_size=50)
        items = [SampleItem(id=1, name="Only One")]
        response = PaginatedResponse[SampleItem].create(items, 1, params)

        assert response.pagination.total == 1
        assert response.pagination.total_pages == 1
        assert response.pagination.has_next is False
        assert response.pagination.has_prev is False

    def test_page_size_equals_total(self):
        """Test wenn page_size == total"""
        params = PaginationParams(page=1, page_size=50)
        response = PaginatedResponse[SampleItem].create([], 50, params)

        assert response.pagination.total_pages == 1
        assert response.pagination.has_next is False
