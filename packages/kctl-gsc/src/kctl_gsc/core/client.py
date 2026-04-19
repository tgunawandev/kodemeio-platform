"""Google Search Console API v1 client (service-account auth)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from google.oauth2 import service_account  # type: ignore[import-untyped]
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from kctl_lib.exceptions import AuthenticationError, KctlError
from kctl_lib.exceptions import NotFoundError as KctlNotFoundError

SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/webmasters",
]


class GSCCredentialsError(KctlError):
    """Service-account credentials file missing or unparseable."""


class GSCPropertyForbidden(KctlError):
    """Service-account email not added as a user on this property."""

    def __init__(self, property_uri: str, sa_email: str | None = None) -> None:
        self.property_uri = property_uri
        self.sa_email = sa_email
        msg = f"403 on {property_uri}"
        if sa_email:
            msg += f" — add {sa_email} as a user in Search Console"
        super().__init__(msg)


class GSCClient:
    def __init__(self, credentials_file: str) -> None:
        if not credentials_file:
            raise GSCCredentialsError("No credentials_file configured. Run: kctl-gsc config init")
        path = Path(credentials_file).expanduser()
        if not path.is_file():
            raise GSCCredentialsError(f"Credentials file not found: {path}")
        try:
            self._creds = service_account.Credentials.from_service_account_file(str(path), scopes=SCOPES)
        except ValueError as e:
            raise GSCCredentialsError(f"Invalid service-account file: {e}") from e
        self.service_account_email: str = getattr(self._creds, "service_account_email", "")
        self._service = build("searchconsole", "v1", credentials=self._creds, cache_discovery=False)

    # ------------------------------------------------------------------ #
    # Resource accessors                                                  #
    # ------------------------------------------------------------------ #
    def sites(self) -> Any:
        return self._service.sites()

    def searchanalytics(self) -> Any:
        return self._service.searchanalytics()

    def sitemaps(self) -> Any:
        return self._service.sitemaps()

    def url_inspection(self) -> Any:
        return self._service.urlInspection().index()

    # ------------------------------------------------------------------ #
    # Diagnostics                                                         #
    # ------------------------------------------------------------------ #
    def check_auth(self) -> dict[str, Any]:
        try:
            return self.sites().list().execute() or {}
        except HttpError as e:
            raise self._map_http_error(e, property_uri="<sites.list>") from e

    def _map_http_error(self, e: HttpError, property_uri: str) -> KctlError:
        status = getattr(e.resp, "status", 0)
        if status == 401:
            return AuthenticationError("401 unauthorized — credentials rejected")
        if status == 403:
            return GSCPropertyForbidden(property_uri, self.service_account_email)
        if status == 404:
            return KctlNotFoundError("property", property_uri)
        return KctlError(f"Search Console API error {status}: {e}")
