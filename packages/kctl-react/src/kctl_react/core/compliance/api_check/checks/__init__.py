"""API check registry — all 6 checkers."""

from .endpoints import EndpointChecker
from .envelope import EnvelopeChecker
from .naming import NamingChecker
from .params import ParamChecker
from .requests import RequestChecker
from .types import TypeChecker

ALL_API_CHECKERS = [
    EndpointChecker(),
    TypeChecker(),
    RequestChecker(),
    ParamChecker(),
    EnvelopeChecker(),
    NamingChecker(),
]
CHECKER_MAP = {c.name: c for c in ALL_API_CHECKERS}
