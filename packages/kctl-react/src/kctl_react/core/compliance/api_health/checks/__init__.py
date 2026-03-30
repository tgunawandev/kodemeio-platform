"""API health check registry — all 4 checkers."""

from .auth import AuthChecker
from .reachable import ReachableChecker
from .response import ResponseChecker
from .timing import TimingChecker

ALL_HEALTH_CHECKERS = [AuthChecker(), ReachableChecker(), ResponseChecker(), TimingChecker()]
CHECKER_MAP = {c.name: c for c in ALL_HEALTH_CHECKERS}
