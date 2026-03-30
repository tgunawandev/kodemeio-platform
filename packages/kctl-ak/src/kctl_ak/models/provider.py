"""Provider models (OAuth2, LDAP, SAML, Proxy)."""

from __future__ import annotations

from pydantic import BaseModel


class OAuth2Provider(BaseModel):
    pk: int
    name: str
    client_id: str = ""
    client_secret: str | None = None
    client_type: str = "confidential"
    redirect_uris: str = ""
    authorization_flow: str | None = None
    sub_mode: str | None = None
    access_token_validity: str | None = None


class OAuth2ProviderCreate(BaseModel):
    name: str
    redirect_uris: str
    client_type: str = "confidential"
    authorization_flow: str


class LDAPProvider(BaseModel):
    pk: int
    name: str
    base_dn: str = ""
    authorization_flow: str | None = None


class SAMLProvider(BaseModel):
    pk: int
    name: str
    acs_url: str | None = None
    issuer: str | None = None
    authorization_flow: str | None = None


class ProxyProvider(BaseModel):
    pk: int
    name: str
    external_host: str = ""
    internal_host: str | None = None
    mode: str = "forward_single"
    authorization_flow: str | None = None


class ProxyProviderCreate(BaseModel):
    name: str
    external_host: str
    internal_host: str = ""
    mode: str = "forward_single"
    authorization_flow: str
