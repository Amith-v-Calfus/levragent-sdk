import pytest
from pydantic import BaseModel, ValidationError

import levragent
from levragent import File, Image

VALID_DATA_URI_IMAGE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA"
VALID_DATA_URI_FILE = "data:application/pdf;base64,JVBERi0xLjQKJeLjz9M"
VALID_URL = "https://storage.example.com/file123.pdf"
INVALID_VALUE = "not-a-valid-reference"


class ImageModel(BaseModel):
    photo: Image


class FileModel(BaseModel):
    document: File


def test_image_accepts_valid_data_uri():
    model = ImageModel(photo=VALID_DATA_URI_IMAGE)
    assert model.photo == VALID_DATA_URI_IMAGE


def test_image_accepts_valid_http_url():
    model = ImageModel(photo=VALID_URL)
    assert model.photo == VALID_URL


def test_image_rejects_invalid_string():
    with pytest.raises(ValidationError, match="base64 data URI"):
        ImageModel(photo=INVALID_VALUE)


def test_file_accepts_valid_data_uri():
    model = FileModel(document=VALID_DATA_URI_FILE)
    assert model.document == VALID_DATA_URI_FILE


def test_file_accepts_valid_http_url():
    model = FileModel(document=VALID_URL)
    assert model.document == VALID_URL


def test_file_rejects_invalid_string():
    with pytest.raises(ValidationError, match="base64 data URI"):
        FileModel(document=INVALID_VALUE)


def test_image_and_file_are_distinguished_in_schema_dict():
    class MixedInput(BaseModel):
        photo: Image
        document: File
        caption: str

    class MixedOutput(BaseModel):
        ok: bool

    @levragent.agent(input_schema=MixedInput, output_schema=MixedOutput)
    def run(input: MixedInput) -> MixedOutput:
        return MixedOutput(ok=True)

    assert run.input_schema_dict() == {"photo": "image", "document": "file", "caption": "str"}


def test_plain_str_field_still_reports_as_str_not_image_or_file():
    class PlainInput(BaseModel):
        name: str

    class PlainOutput(BaseModel):
        ok: bool

    @levragent.agent(input_schema=PlainInput, output_schema=PlainOutput)
    def run(input: PlainInput) -> PlainOutput:
        return PlainOutput(ok=True)

    assert run.input_schema_dict() == {"name": "str"}


def test_handle_request_accepts_valid_image_payload():
    class Input(BaseModel):
        photo: Image

    class Output(BaseModel):
        ok: bool

    @levragent.agent(input_schema=Input, output_schema=Output)
    def run(input: Input) -> Output:
        return Output(ok=True)

    status_code, body = run.handle_request({"photo": VALID_DATA_URI_IMAGE})
    assert status_code == 200
    assert body == {"ok": True}


def test_handle_request_rejects_invalid_image_payload():
    class Input(BaseModel):
        photo: Image

    class Output(BaseModel):
        ok: bool

    @levragent.agent(input_schema=Input, output_schema=Output)
    def run(input: Input) -> Output:
        return Output(ok=True)

    status_code, body = run.handle_request({"photo": INVALID_VALUE})
    assert status_code == 400
    assert body["error"]["type"] == "validation_error"
