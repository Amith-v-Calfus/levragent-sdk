from __future__ import annotations

from typing import Any, Callable, TypeVar

from pydantic import AfterValidator, BaseModel
from pydantic import ValidationError as PydanticValidationError

from .errors import error_body
from .types import validate_file, validate_image

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class Agent:
    """Wraps a plain function into a Levragent-compliant agent.

    Built by the `@levragent.agent(...)` decorator; not instantiated directly.
    """

    def __init__(
        self,
        func: Callable[[InputT], OutputT | dict],
        *,
        input_schema: type[BaseModel],
        output_schema: type[BaseModel],
        name: str,
        description: str | None = None,
        domain: str | None = None,
        creator_name: str | None = None,
    ) -> None:
        self.func = func
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.name = name
        self.description = description
        self.domain = domain
        self.creator_name = creator_name
        self.__name__ = getattr(func, "__name__", name)
        self.__doc__ = func.__doc__

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)

    def handle_request(self, payload: dict) -> tuple[int, dict]:
        """Validate `payload`, run the wrapped function, validate its output.

        Returns (status_code, json_body) so server.py / lambda_handler.py can
        adapt the same core logic to their own transport without duplicating it.
        """
        try:
            input_instance = self.input_schema.model_validate(payload)
        except PydanticValidationError as exc:
            return 400, error_body(
                "validation_error", "Input did not match input_schema", errors=exc.errors()
            )

        try:
            result = self.func(input_instance)
        except Exception as exc:  # noqa: BLE001 - creator's function body is arbitrary
            return 500, error_body("execution_error", str(exc))

        try:
            output_instance = (
                result
                if isinstance(result, self.output_schema)
                else self.output_schema.model_validate(result)
            )
        except PydanticValidationError as exc:
            return 502, error_body(
                "output_validation_error",
                "Agent output did not match output_schema",
                errors=exc.errors(),
            )

        return 200, output_instance.model_dump(mode="json")

    def input_schema_dict(self) -> dict[str, str]:
        return _required_fields(self.input_schema)

    def output_schema_dict(self) -> dict[str, str]:
        return _required_fields(self.output_schema)

    def publish(self, endpoint_url: str, **kwargs: Any) -> dict:
        from .publish import publish as _publish

        return _publish(self, endpoint_url, **kwargs)


def _required_fields(model: type[BaseModel]) -> dict[str, str]:
    # The backend only checks that these keys are present in a payload — it never
    # reads the values or enforces "optional". Fields with a Pydantic default are
    # dropped so the backend's all-required semantics match what the model actually
    # requires.
    return {
        field_name: _type_repr(field)
        for field_name, field in model.model_fields.items()
        if field.is_required()
    }


def _type_repr(field: Any) -> str:
    # Image/File are both Annotated[str, AfterValidator(...)] — indistinguishable
    # from any other Annotated[str, ...] by shape alone. Pydantic also strips the
    # Annotated wrapper off field.annotation (leaving plain `str`) and moves the
    # extras into field.metadata instead, so detection has to look there, keyed
    # off the identity of the specific validator function levragent.types attaches.
    for metadata in field.metadata:
        if isinstance(metadata, AfterValidator):
            if metadata.func is validate_image:
                return "image"
            if metadata.func is validate_file:
                return "file"
    return getattr(field.annotation, "__name__", str(field.annotation))


def agent(
    *,
    input_schema: type[BaseModel],
    output_schema: type[BaseModel],
    name: str | None = None,
    description: str | None = None,
    domain: str | None = None,
    creator_name: str | None = None,
) -> Callable[[Callable[[InputT], OutputT | dict]], Agent]:
    def decorator(func: Callable[[InputT], OutputT | dict]) -> Agent:
        return Agent(
            func,
            input_schema=input_schema,
            output_schema=output_schema,
            name=name or func.__name__,
            description=description,
            domain=domain,
            creator_name=creator_name,
        )

    return decorator
