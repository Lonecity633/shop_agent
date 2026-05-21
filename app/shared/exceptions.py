from dataclasses import dataclass


@dataclass
class ServiceBoundaryError(Exception):
    code: str
    message: str
    status_code: int = 400

