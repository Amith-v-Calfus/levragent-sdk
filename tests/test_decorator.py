from pydantic import BaseModel

import levragent


class WeatherInput(BaseModel):
    city: str
    unit: str = "celsius"


class WeatherOutput(BaseModel):
    temperature: float
    condition: str


@levragent.agent(input_schema=WeatherInput, output_schema=WeatherOutput)
def run(input: WeatherInput) -> WeatherOutput:
    return WeatherOutput(temperature=21.5, condition="Sunny")


def test_decorator_returns_agent_instance():
    assert isinstance(run, levragent.Agent)


def test_agent_name_defaults_to_function_name():
    assert run.name == "run"


def test_agent_name_can_be_overridden():
    @levragent.agent(input_schema=WeatherInput, output_schema=WeatherOutput, name="weather-bot")
    def some_func(input: WeatherInput) -> WeatherOutput:
        return WeatherOutput(temperature=0, condition="Cloudy")

    assert some_func.name == "weather-bot"


def test_agent_is_directly_callable_with_typed_input():
    result = run(WeatherInput(city="Austin"))
    assert result == WeatherOutput(temperature=21.5, condition="Sunny")


def test_handle_request_success():
    status_code, body = run.handle_request({"city": "Austin"})
    assert status_code == 200
    assert body == {"temperature": 21.5, "condition": "Sunny"}


def test_handle_request_optional_field_can_be_omitted():
    status_code, body = run.handle_request({"city": "Austin"})
    assert status_code == 200


def test_handle_request_optional_field_can_be_overridden():
    status_code, body = run.handle_request({"city": "Austin", "unit": "fahrenheit"})
    assert status_code == 200


def test_handle_request_missing_required_field_is_rejected():
    status_code, body = run.handle_request({})
    assert status_code == 400
    assert body["success"] is False
    assert body["error"]["type"] == "validation_error"
    assert "details" in body["error"]


def test_handle_request_wrong_type_is_rejected():
    status_code, body = run.handle_request({"city": 123})
    assert status_code == 400
    assert body["error"]["type"] == "validation_error"


def test_handle_request_non_dict_payload_is_rejected():
    status_code, body = run.handle_request([])
    assert status_code == 400
    assert body["error"]["type"] == "validation_error"


def test_handle_request_execution_error_is_caught():
    @levragent.agent(input_schema=WeatherInput, output_schema=WeatherOutput)
    def broken(input: WeatherInput) -> WeatherOutput:
        raise RuntimeError("boom")

    status_code, body = broken.handle_request({"city": "Austin"})
    assert status_code == 500
    assert body["error"]["type"] == "execution_error"
    assert "boom" in body["error"]["message"]


def test_handle_request_output_validation_error_is_rejected():
    @levragent.agent(input_schema=WeatherInput, output_schema=WeatherOutput)
    def bad_output(input: WeatherInput) -> WeatherOutput:
        return {"temperature": "not-a-number", "condition": "Sunny"}

    status_code, body = bad_output.handle_request({"city": "Austin"})
    assert status_code == 502
    assert body["error"]["type"] == "output_validation_error"


def test_handle_request_accepts_plain_dict_output_matching_schema():
    @levragent.agent(input_schema=WeatherInput, output_schema=WeatherOutput)
    def dict_output(input: WeatherInput) -> WeatherOutput:
        return {"temperature": 10, "condition": "Cloudy"}

    status_code, body = dict_output.handle_request({"city": "Austin"})
    assert status_code == 200
    assert body == {"temperature": 10.0, "condition": "Cloudy"}


def test_input_schema_dict_excludes_fields_with_defaults():
    assert run.input_schema_dict() == {"city": "str"}


def test_output_schema_dict_includes_all_required_fields():
    assert run.output_schema_dict() == {"temperature": "float", "condition": "str"}


def test_schema_dict_is_empty_when_every_field_has_a_default():
    class AllOptional(BaseModel):
        note: str = "n/a"

    @levragent.agent(input_schema=AllOptional, output_schema=WeatherOutput)
    def noop(input: AllOptional) -> WeatherOutput:
        return WeatherOutput(temperature=0, condition="Cloudy")

    assert noop.input_schema_dict() == {}
