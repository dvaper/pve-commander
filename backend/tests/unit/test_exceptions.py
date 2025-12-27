"""
Tests fuer das zentrale Exception-Handling Modul
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException

from app.exceptions import (
    # Base classes
    ErrorDetail,
    ErrorResponse,
    AppException,
    # 400 Bad Request
    ValidationError,
    InvalidRequestError,
    # 401 Unauthorized
    AuthenticationError,
    InvalidCredentialsError,
    TokenExpiredError,
    # 403 Forbidden
    PermissionDeniedError,
    SuperAdminRequiredError,
    # 404 Not Found
    NotFoundError,
    UserNotFoundError,
    VMNotFoundError,
    PlaybookNotFoundError,
    ExecutionNotFoundError,
    # 409 Conflict
    ConflictError,
    DuplicateError,
    # 500 Internal Server Error
    InternalError,
    # 502/503 Service Errors
    ExternalServiceError,
    ProxmoxConnectionError,
    NetBoxConnectionError,
    # Handlers
    app_exception_handler,
    http_exception_handler,
    register_exception_handlers,
)


# =============================================================================
# Tests fuer Error Response Schema
# =============================================================================

class TestErrorDetail:
    """Tests fuer ErrorDetail Schema"""

    def test_error_detail_minimal(self):
        """Test mit nur Pflichtfeldern"""
        detail = ErrorDetail(error_code="TEST_ERROR", message="Test message")
        assert detail.error_code == "TEST_ERROR"
        assert detail.message == "Test message"
        assert detail.details is None

    def test_error_detail_with_details(self):
        """Test mit optionalem details-Feld"""
        detail = ErrorDetail(
            error_code="TEST_ERROR",
            message="Test message",
            details={"field": "value", "count": 42}
        )
        assert detail.details == {"field": "value", "count": 42}


class TestErrorResponse:
    """Tests fuer ErrorResponse Schema"""

    def test_error_response_structure(self):
        """Test der Wrapper-Struktur"""
        detail = ErrorDetail(error_code="TEST", message="msg")
        response = ErrorResponse(error=detail)
        assert response.error.error_code == "TEST"


# =============================================================================
# Tests fuer Base Exception
# =============================================================================

class TestAppException:
    """Tests fuer AppException Basis-Klasse"""

    def test_app_exception_basic(self):
        """Test der Basis-Exception"""
        exc = AppException(
            status_code=418,
            error_code="TEAPOT",
            message="I'm a teapot"
        )
        assert exc.status_code == 418
        assert exc.error_code == "TEAPOT"
        assert exc.message == "I'm a teapot"
        assert exc.details is None

    def test_app_exception_with_details(self):
        """Test mit zusaetzlichen Details"""
        exc = AppException(
            status_code=400,
            error_code="BAD",
            message="Bad request",
            details={"field": "username", "reason": "too short"}
        )
        assert exc.details == {"field": "username", "reason": "too short"}
        assert exc.detail["details"] == {"field": "username", "reason": "too short"}

    def test_app_exception_inherits_http_exception(self):
        """Test dass AppException von HTTPException erbt"""
        exc = AppException(400, "TEST", "msg")
        assert isinstance(exc, HTTPException)


# =============================================================================
# Tests fuer 400 Bad Request Exceptions
# =============================================================================

class TestValidationError:
    """Tests fuer ValidationError"""

    def test_validation_error_basic(self):
        """Test mit Standard-Werten"""
        exc = ValidationError("Field required")
        assert exc.status_code == 400
        assert exc.error_code == "VALIDATION_ERROR"
        assert exc.message == "Field required"

    def test_validation_error_with_details(self):
        """Test mit Details"""
        exc = ValidationError(
            "Validation failed",
            details={"field": "email", "error": "invalid format"}
        )
        assert exc.details == {"field": "email", "error": "invalid format"}


class TestInvalidRequestError:
    """Tests fuer InvalidRequestError"""

    def test_invalid_request_error(self):
        """Test der InvalidRequestError"""
        exc = InvalidRequestError("Missing parameter")
        assert exc.status_code == 400
        assert exc.error_code == "INVALID_REQUEST"


# =============================================================================
# Tests fuer 401 Unauthorized Exceptions
# =============================================================================

class TestAuthenticationError:
    """Tests fuer AuthenticationError"""

    def test_authentication_error_default_message(self):
        """Test mit Standard-Nachricht"""
        exc = AuthenticationError()
        assert exc.status_code == 401
        assert exc.error_code == "AUTHENTICATION_REQUIRED"
        assert exc.message == "Authentifizierung erforderlich"

    def test_authentication_error_custom_message(self):
        """Test mit eigener Nachricht"""
        exc = AuthenticationError("Please login first")
        assert exc.message == "Please login first"


class TestInvalidCredentialsError:
    """Tests fuer InvalidCredentialsError"""

    def test_invalid_credentials_default(self):
        """Test mit Standard-Nachricht"""
        exc = InvalidCredentialsError()
        assert exc.status_code == 401
        assert exc.error_code == "INVALID_CREDENTIALS"
        assert "Passwort" in exc.message


class TestTokenExpiredError:
    """Tests fuer TokenExpiredError"""

    def test_token_expired_error(self):
        """Test der TokenExpiredError"""
        exc = TokenExpiredError()
        assert exc.status_code == 401
        assert exc.error_code == "TOKEN_EXPIRED"


# =============================================================================
# Tests fuer 403 Forbidden Exceptions
# =============================================================================

class TestPermissionDeniedError:
    """Tests fuer PermissionDeniedError"""

    def test_permission_denied_default(self):
        """Test mit Standard-Nachricht"""
        exc = PermissionDeniedError()
        assert exc.status_code == 403
        assert exc.error_code == "PERMISSION_DENIED"

    def test_permission_denied_with_resource(self):
        """Test mit Ressourcen-Info"""
        exc = PermissionDeniedError(
            message="Cannot delete VM",
            resource="vm-100"
        )
        assert exc.details == {"resource": "vm-100"}


class TestSuperAdminRequiredError:
    """Tests fuer SuperAdminRequiredError"""

    def test_super_admin_required(self):
        """Test der SuperAdminRequiredError"""
        exc = SuperAdminRequiredError()
        assert exc.status_code == 403
        assert exc.error_code == "SUPER_ADMIN_REQUIRED"


# =============================================================================
# Tests fuer 404 Not Found Exceptions
# =============================================================================

class TestNotFoundError:
    """Tests fuer NotFoundError"""

    def test_not_found_error_generic(self):
        """Test der generischen NotFoundError"""
        exc = NotFoundError("VM", 100)
        assert exc.status_code == 404
        assert exc.error_code == "VM_NOT_FOUND"
        assert "100" in exc.message
        assert exc.details["resource_type"] == "VM"
        assert exc.details["resource_id"] == "100"

    def test_not_found_error_custom_message(self):
        """Test mit eigener Nachricht"""
        exc = NotFoundError("Template", "ubuntu-22.04", message="Template unavailable")
        assert exc.message == "Template unavailable"


class TestSpecificNotFoundErrors:
    """Tests fuer spezifische NotFound-Exceptions"""

    def test_user_not_found(self):
        """Test UserNotFoundError"""
        exc = UserNotFoundError(42)
        assert exc.error_code == "USER_NOT_FOUND"
        assert exc.details["resource_type"] == "User"

    def test_vm_not_found(self):
        """Test VMNotFoundError"""
        exc = VMNotFoundError("vm-123")
        assert exc.error_code == "VM_NOT_FOUND"

    def test_playbook_not_found(self):
        """Test PlaybookNotFoundError"""
        exc = PlaybookNotFoundError("setup.yml")
        assert exc.error_code == "PLAYBOOK_NOT_FOUND"

    def test_execution_not_found(self):
        """Test ExecutionNotFoundError"""
        exc = ExecutionNotFoundError("exec-456")
        assert exc.error_code == "EXECUTION_NOT_FOUND"


# =============================================================================
# Tests fuer 409 Conflict Exceptions
# =============================================================================

class TestConflictError:
    """Tests fuer ConflictError"""

    def test_conflict_error_basic(self):
        """Test ohne Ressourcen-Typ"""
        exc = ConflictError("Resource already exists")
        assert exc.status_code == 409
        assert exc.error_code == "CONFLICT"

    def test_conflict_error_with_resource_type(self):
        """Test mit Ressourcen-Typ"""
        exc = ConflictError("User exists", resource_type="User")
        assert exc.error_code == "USER_CONFLICT"


class TestDuplicateError:
    """Tests fuer DuplicateError"""

    def test_duplicate_error(self):
        """Test der DuplicateError"""
        exc = DuplicateError("User", "email", "test@example.com")
        assert exc.status_code == 409
        assert "email" in exc.message
        assert "test@example.com" in exc.message
        assert exc.details["field"] == "email"


# =============================================================================
# Tests fuer 500 Internal Server Error Exceptions
# =============================================================================

class TestInternalError:
    """Tests fuer InternalError"""

    def test_internal_error_default(self):
        """Test mit Standard-Nachricht"""
        exc = InternalError()
        assert exc.status_code == 500
        assert exc.error_code == "INTERNAL_ERROR"

    def test_internal_error_with_details(self):
        """Test mit Details"""
        exc = InternalError(
            message="Database connection failed",
            details={"database": "postgres", "error": "timeout"}
        )
        assert exc.details["database"] == "postgres"


# =============================================================================
# Tests fuer 502/503 Service Exceptions
# =============================================================================

class TestExternalServiceError:
    """Tests fuer ExternalServiceError"""

    def test_external_service_error(self):
        """Test der generischen ExternalServiceError"""
        exc = ExternalServiceError("Redis")
        assert exc.status_code == 502
        assert exc.error_code == "REDIS_UNAVAILABLE"
        assert "Redis" in exc.message


class TestProxmoxConnectionError:
    """Tests fuer ProxmoxConnectionError"""

    def test_proxmox_connection_error_default(self):
        """Test mit Standard-Nachricht"""
        exc = ProxmoxConnectionError()
        assert exc.status_code == 502
        assert exc.error_code == "PROXMOX_UNAVAILABLE"

    def test_proxmox_connection_error_custom(self):
        """Test mit eigener Nachricht"""
        exc = ProxmoxConnectionError("Node pve-node-01 unreachable")
        assert exc.message == "Node pve-node-01 unreachable"


class TestNetBoxConnectionError:
    """Tests fuer NetBoxConnectionError"""

    def test_netbox_connection_error(self):
        """Test der NetBoxConnectionError"""
        exc = NetBoxConnectionError()
        assert exc.error_code == "NETBOX_UNAVAILABLE"


# =============================================================================
# Tests fuer Exception Handlers
# =============================================================================

class TestExceptionHandlers:
    """Tests fuer die FastAPI Exception-Handler"""

    @pytest.mark.asyncio
    async def test_app_exception_handler(self):
        """Test des AppException Handlers"""
        request = MagicMock()
        exc = ValidationError("Field invalid", details={"field": "email"})

        response = await app_exception_handler(request, exc)

        assert response.status_code == 400
        # JSONResponse body ist bytes, muss dekodiert werden
        import json
        body = json.loads(response.body)
        assert body["error"]["error_code"] == "VALIDATION_ERROR"
        assert body["error"]["message"] == "Field invalid"
        assert body["error"]["details"]["field"] == "email"

    @pytest.mark.asyncio
    async def test_http_exception_handler_dict_detail(self):
        """Test des HTTP Exception Handlers mit dict detail"""
        request = MagicMock()
        exc = HTTPException(
            status_code=400,
            detail={"error_code": "CUSTOM", "message": "Custom error", "details": None}
        )

        response = await http_exception_handler(request, exc)

        import json
        body = json.loads(response.body)
        assert body["error"]["error_code"] == "CUSTOM"

    @pytest.mark.asyncio
    async def test_http_exception_handler_string_detail(self):
        """Test des HTTP Exception Handlers mit string detail"""
        request = MagicMock()
        exc = HTTPException(status_code=404, detail="Not found")

        response = await http_exception_handler(request, exc)

        import json
        body = json.loads(response.body)
        assert body["error"]["error_code"] == "HTTP_404"
        assert body["error"]["message"] == "Not found"


class TestRegisterExceptionHandlers:
    """Tests fuer die Handler-Registrierung"""

    def test_register_exception_handlers(self):
        """Test dass Handler registriert werden"""
        mock_app = MagicMock()

        register_exception_handlers(mock_app)

        # Sollte add_exception_handler zweimal aufrufen
        assert mock_app.add_exception_handler.call_count == 2
