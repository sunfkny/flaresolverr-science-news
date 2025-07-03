"""
`FlareSolverr <https://github.com/FlareSolverr/FlareSolverr>`_ Python Client
=======================

Installation by docker
-----------------------

.. code-block:: shell
    docker run -it --rm --name=flaresolverr -p 8191:8191 -e LOG_LEVEL=info -e TEST_URL=https://www.example.com --add-host=host.docker.internal:host-gateway ghcr.io/flaresolverr/flaresolverr:latest

"""

import typing
from typing import Annotated, Literal, NotRequired, TypedDict
from urllib.parse import urljoin

import pydantic
import requests

STATUS_OK = "ok"
STATUS_ERROR = "error"


class Cookie(pydantic.BaseModel):
    domain: str
    httpOnly: bool
    name: str
    path: str
    sameSite: str
    secure: bool
    value: str

    expires: float | None = pydantic.Field(None, repr=False)
    size: int | None = pydantic.Field(None, repr=False)
    session: bool | None = pydantic.Field(None, repr=False)


class Solution(pydantic.BaseModel):
    url: str
    status: int
    headers: dict
    response: str = pydantic.Field(repr=False)
    cookies: list[Cookie]
    userAgent: str


class ResponseOk(pydantic.BaseModel):
    status: Literal["ok"]
    solution: Solution
    message: str
    startTimestamp: int
    endTimestamp: int
    version: str

    def unwrap_response_ok(self):
        return self


class ResponseError(pydantic.BaseModel):
    status: Literal["error"]
    message: str
    startTimestamp: int
    endTimestamp: int
    version: str

    def unwrap_response_ok(self):
        raise ValueError(self.message)


class ResponseException(pydantic.BaseModel):
    status: Literal[None] = pydantic.Field(None, repr=False)
    error: str

    def unwrap_response_ok(self):
        raise ValueError(self.error)


Response = Annotated[
    ResponseOk | ResponseError | ResponseException,
    pydantic.Field(discriminator="status"),
]

ResponseAdapter = pydantic.TypeAdapter[Response](Response)


class Proxy(TypedDict):
    url: str
    username: NotRequired[str | None]
    password: NotRequired[str | None]


class RequestGetParameter(TypedDict):
    """
    https://github.com/FlareSolverr/FlareSolverr?tab=readme-ov-file#-requestget

    | Parameter           | Notes                                                                                                                                                                                                                                                                                                                                        |
    |---------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
    | url                 | Mandatory                                                                                                                                                                                                                                                                                                                                    |
    | session             | Optional. Will send the request from and existing browser instance. If one is not sent it will create a temporary instance that will be destroyed immediately after the request is completed.                                                                                                                                                |
    | session_ttl_minutes | Optional. FlareSolverr will automatically rotate expired sessions based on the TTL provided in minutes.                                                                                                                                                                                                                                      |
    | maxTimeout          | Optional, default value 60000. Max timeout to solve the challenge in milliseconds.                                                                                                                                                                                                                                                           |
    | cookies             | Optional. Will be used by the headless browser. Eg: `"cookies": [{"name": "cookie1", "value": "value1"}, {"name": "cookie2", "value": "value2"}]`.                                                                                                                                                                                           |
    | returnOnlyCookies   | Optional, default false. Only returns the cookies. Response data, headers and other parts of the response are removed.                                                                                                                                                                                                                       |
    | proxy               | Optional, default disabled. Eg: `"proxy": {"url": "http://127.0.0.1:8888"}`. You must include the proxy schema in the URL: `http://`, `socks4://` or `socks5://`. Authorization (username/password) is not supported. (When the `session` parameter is set, the proxy is ignored; a session specific proxy can be set in `sessions.create`.) |

    """

    url: str
    session: NotRequired[str | None]
    session_ttl_minutes: NotRequired[int | None]
    maxTimeout: NotRequired[int | None]
    cookies: NotRequired[list[dict[str, str]] | None]
    returnOnlyCookies: NotRequired[bool | None]
    proxy: NotRequired[Proxy | None]


class IndexResponse(pydantic.BaseModel):
    msg: str
    version: str
    userAgent: str


class HealthResponse(pydantic.BaseModel):
    status: str

    def is_ok(self) -> bool:
        return self.status == STATUS_OK


class FlareSolverrRequest:
    def __init__(self, session: requests.Session, base_url: str):
        self.session = session
        self.base_url = base_url
        self.controller_v1 = urljoin(self.base_url, "/v1")

    def get(self, **kwargs: typing.Unpack[RequestGetParameter]):
        r = self.session.post(self.controller_v1, json={"cmd": "request.get", **kwargs})
        return ResponseAdapter.validate_json(r.text)


class FlareSolverr:
    def __init__(self, base_url: str = "http://127.0.0.1:8191/"):
        self.base_url = base_url
        self.session = requests.Session()
        self.request = FlareSolverrRequest(self.session, base_url)
        assert self.health().is_ok(), "FlareSolverr is not running"

    def index(self):
        res = self.session.get(self.base_url)
        res.raise_for_status()
        return IndexResponse.model_validate_json(res.text)

    def health(self):
        res = self.session.get(f"{self.base_url}/health")
        res.raise_for_status()
        return HealthResponse.model_validate_json(res.text)
