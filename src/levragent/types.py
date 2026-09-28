from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator

# Regex-only: we validate that a value *looks like* a data URI or an http(s)
# URL, we never decode/fetch it to inspect the actual file content.
_DATA_URI_RE = re.compile(r"^data:[\w.+-]+/[\w.+-]+;base64,[A-Za-z0-9+/]+=*$")
_HTTP_URL_RE = re.compile(r"^https?://\S+$")


def _is_data_uri_or_url(value: str) -> bool:
    return bool(_DATA_URI_RE.match(value) or _HTTP_URL_RE.match(value))


# Two distinct functions (not one shared one aliased twice) so decorator.py's
# _type_repr() can tell Image and File apart by identity of the validator
# attached to the Annotated[...] metadata.
def validate_image(value: str) -> str:
    if not _is_data_uri_or_url(value):
        raise ValueError(
            "must be a base64 data URI (e.g. 'data:image/png;base64,...') or an http(s) URL"
        )
    return value


def validate_file(value: str) -> str:
    if not _is_data_uri_or_url(value):
        raise ValueError(
            "must be a base64 data URI (e.g. 'data:application/pdf;base64,...') or an http(s) URL"
        )
    return value


Image = Annotated[str, AfterValidator(validate_image)]
File = Annotated[str, AfterValidator(validate_file)]
