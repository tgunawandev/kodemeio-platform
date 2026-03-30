"""Compliance checkers registry."""

from __future__ import annotations

from .api import ApiChecker
from .codegen import CodegenChecker
from .darkmode import DarkmodeChecker
from .errors import ErrorsChecker
from .features import FeaturesChecker
from .i18n_check import I18nChecker
from .imports import ImportsChecker
from .navigation import NavigationChecker
from .practices import PracticesChecker
from .providers import ProviderChecker
from .pwa import PwaChecker
from .responsive import ResponsiveChecker
from .scripts import ScriptsChecker
from .shadcn import ShadcnChecker
from .structure import StructureChecker
from .testing import TestingChecker
from .theme import ThemeChecker
from .ui_standard import UiStandardChecker
from .vite import ViteChecker

ALL_CHECKERS = [
    StructureChecker(),
    ProviderChecker(),
    ShadcnChecker(),
    ImportsChecker(),
    CodegenChecker(),
    I18nChecker(),
    FeaturesChecker(),
    ThemeChecker(),
    ResponsiveChecker(),
    DarkmodeChecker(),
    NavigationChecker(),
    ErrorsChecker(),
    ApiChecker(),
    PwaChecker(),
    ViteChecker(),
    ScriptsChecker(),
    TestingChecker(),
    PracticesChecker(),
    UiStandardChecker(),
]

CHECKER_MAP = {c.name: c.check for c in ALL_CHECKERS}
