"""
Zentrale Exception-Definitionen fuer PVE Commander

Dieses Modul definiert:
- Custom Exception-Klassen fuer verschiedene Fehlerkategorien
- Einheitliche Error-Response-Formate
- Exception-Handler fuer FastAPI
"""
from typing import Any, Optional
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


# =============================================================================
# Error Response Schema
# =============================================================================

class ErrorDetail(BaseModel):
    """Einheitliches Error-Response-Format"""
    error_code: str
    message: str
    details: Optional[dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Wrapper fuer Error-Responses"""
    error: ErrorDetail


# =============================================================================
# Custom Exception Classes
# =============================================================================

class AppException(HTTPException):
    """
    Basis-Exception fuer alle App-spezifischen Fehler.

    Erweitert HTTPException um:
    - error_code: Eindeutiger Fehlercode (z.B. "VM_NOT_FOUND")
    - details: Zusaetzliche Fehlerinformationen
    """

    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ):
        self.error_code = error_code
        self.message = message
        self.details = details
        super().__init__(
            status_code=status_code,
            detail={
                "error_code": error_code,
                "message": message,
                "details": details,
            }
        )


# -----------------------------------------------------------------------------
# 400 Bad Request
# -----------------------------------------------------------------------------

class ValidationError(AppException):
    """Validierungsfehler (400)"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            status_code=400,
            error_code="VALIDATION_ERROR",
            message=message,
            details=details,
        )


class InvalidRequestError(AppException):
    """Ungueltige Anfrage (400)"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            status_code=400,
            error_code="INVALID_REQUEST",
            message=message,
            details=details,
        )


# -----------------------------------------------------------------------------
# 401 Unauthorized
# -----------------------------------------------------------------------------

class AuthenticationError(AppException):
    """Authentifizierung fehlgeschlagen (401)"""

    def __init__(self, message: str = "Authentifizierung erforderlich"):
        super().__init__(
            status_code=401,
            error_code="AUTHENTICATION_REQUIRED",
            message=message,
        )


class InvalidCredentialsError(AppException):
    """Ungueltige Anmeldedaten (401)"""

    def __init__(self, message: str = "Falscher Benutzername oder Passwort"):
        super().__init__(
            status_code=401,
            error_code="INVALID_CREDENTIALS",
            message=message,
        )


class TokenExpiredError(AppException):
    """Token abgelaufen (401)"""

    def __init__(self, message: str = "Token ist abgelaufen"):
        super().__init__(
            status_code=401,
            error_code="TOKEN_EXPIRED",
            message=message,
        )


# -----------------------------------------------------------------------------
# 403 Forbidden
# -----------------------------------------------------------------------------

class PermissionDeniedError(AppException):
    """Keine Berechtigung (403)"""

    def __init__(
        self,
        message: str = "Keine Berechtigung fuer diese Aktion",
        resource: Optional[str] = None,
    ):
        details = {"resource": resource} if resource else None
        super().__init__(
            status_code=403,
            error_code="PERMISSION_DENIED",
            message=message,
            details=details,
        )


class SuperAdminRequiredError(AppException):
    """Super-Admin erforderlich (403)"""

    def __init__(self, message: str = "Diese Aktion erfordert Super-Admin-Rechte"):
        super().__init__(
            status_code=403,
            error_code="SUPER_ADMIN_REQUIRED",
            message=message,
        )


# -----------------------------------------------------------------------------
# 404 Not Found
# -----------------------------------------------------------------------------

class NotFoundError(AppException):
    """Ressource nicht gefunden (404)"""

    def __init__(
        self,
        resource_type: str,
        resource_id: Any,
        message: Optional[str] = None,
    ):
        msg = message or f"{resource_type} mit ID '{resource_id}' nicht gefunden"
        super().__init__(
            status_code=404,
            error_code=f"{resource_type.upper()}_NOT_FOUND",
            message=msg,
            details={"resource_type": resource_type, "resource_id": str(resource_id)},
        )


class UserNotFoundError(NotFoundError):
    """Benutzer nicht gefunden (404)"""

    def __init__(self, user_id: Any):
        super().__init__("User", user_id)


class VMNotFoundError(NotFoundError):
    """VM nicht gefunden (404)"""

    def __init__(self, vm_id: Any):
        super().__init__("VM", vm_id)


class PlaybookNotFoundError(NotFoundError):
    """Playbook nicht gefunden (404)"""

    def __init__(self, playbook_name: str):
        super().__init__("Playbook", playbook_name)


class ExecutionNotFoundError(NotFoundError):
    """Execution nicht gefunden (404)"""

    def __init__(self, execution_id: Any):
        super().__init__("Execution", execution_id)


# -----------------------------------------------------------------------------
# 409 Conflict
# -----------------------------------------------------------------------------

class ConflictError(AppException):
    """Konflikt/Duplikat (409)"""

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        details: Optional[dict] = None,
    ):
        error_code = f"{resource_type.upper()}_CONFLICT" if resource_type else "CONFLICT"
        super().__init__(
            status_code=409,
            error_code=error_code,
            message=message,
            details=details,
        )


class DuplicateError(ConflictError):
    """Duplikat-Fehler (409)"""

    def __init__(self, resource_type: str, field: str, value: Any):
        super().__init__(
            message=f"{resource_type} mit {field}='{value}' existiert bereits",
            resource_type=resource_type,
            details={"field": field, "value": str(value)},
        )


# -----------------------------------------------------------------------------
# 500 Internal Server Error
# -----------------------------------------------------------------------------

class InternalError(AppException):
    """Interner Serverfehler (500)"""

    def __init__(
        self,
        message: str = "Ein interner Fehler ist aufgetreten",
        details: Optional[dict] = None,
    ):
        super().__init__(
            status_code=500,
            error_code="INTERNAL_ERROR",
            message=message,
            details=details,
        )


# -----------------------------------------------------------------------------
# 502/503 Service Errors
# -----------------------------------------------------------------------------

class ExternalServiceError(AppException):
    """Externer Service nicht erreichbar (502)"""

    def __init__(
        self,
        service_name: str,
        message: Optional[str] = None,
        details: Optional[dict] = None,
    ):
        msg = message or f"Verbindung zu {service_name} fehlgeschlagen"
        super().__init__(
            status_code=502,
            error_code=f"{service_name.upper()}_UNAVAILABLE",
            message=msg,
            details=details,
        )


class ProxmoxConnectionError(ExternalServiceError):
    """Proxmox nicht erreichbar (502)"""

    def __init__(self, message: Optional[str] = None):
        super().__init__("Proxmox", message)


class NetBoxConnectionError(ExternalServiceError):
    """NetBox nicht erreichbar (502)"""

    def __init__(self, message: Optional[str] = None):
        super().__init__("NetBox", message)


# =============================================================================
# Exception Handlers fuer FastAPI
# =============================================================================

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handler fuer AppException und Subklassen"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "error_code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handler fuer Standard-HTTPException (Fallback)"""
    # Wenn detail bereits ein dict ist, verwende es
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail},
        )

    # Sonst: Einfache Nachricht in einheitliches Format wandeln
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "error_code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
                "details": None,
            }
        },
    )


def register_exception_handlers(app):
    """
    Registriert alle Exception-Handler bei der FastAPI-App.

    Aufruf in main.py:
        from app.exceptions import register_exception_handlers
        register_exception_handlers(app)
    """
    from fastapi import HTTPException

    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
