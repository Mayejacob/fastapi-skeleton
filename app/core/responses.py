from typing import Any, Generic, TypeVar

from fastapi import status
from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool
    message: str = ""
    data: T | None = None
    status_code: int = status.HTTP_200_OK


def send_success(
    message: str = "Success", data: Any = None, status_code: int = status.HTTP_200_OK
) -> APIResponse:
    return APIResponse(
        success=True, message=message, data=data, status_code=status_code
    )


def send_error(
    message: str = "Error",
    data: Any = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> APIResponse:
    return APIResponse(
        success=False, message=message, data=data, status_code=status_code
    )
