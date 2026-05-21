from fastapi import HTTPException, status


class APIError(HTTPException):
    def __init__(self, code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail={"code": code, "message": message})


def raise_error(code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
    raise APIError(code=code, message=message, status_code=status_code)
