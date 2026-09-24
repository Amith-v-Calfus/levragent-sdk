# levragent

Python SDK for building and publishing agents to the [Levragent](https://github.com/Amith-v-Calfus/AgentBazaar) marketplace.

Turn a plain Python function into a marketplace-compliant agent with one decorator:

```python
from pydantic import BaseModel
import levragent


class WeatherInput(BaseModel):
    city: str


class WeatherOutput(BaseModel):
    temperature: float
    condition: str


@levragent.agent(input_schema=WeatherInput, output_schema=WeatherOutput)
def run(input: WeatherInput) -> WeatherOutput:
    return WeatherOutput(temperature=21.5, condition="Sunny")
```

`@levragent.agent(...)` validates input and output against your Pydantic
models on every call and catches exceptions from your function, returning a
standard error shape instead of raising. Fields with a default are treated
as optional; fields without one are required.

## Running it locally

```python
from levragent.server import serve

serve(run, port=8001)
```

This starts a stdlib `http.server` exposing `POST /run` and `GET /health` —
no framework dependency needed to try an agent out.

## Deploying to AWS Lambda

```python
from levragent.lambda_handler import make_handler

handler = make_handler(run)
```

Point your Lambda Function URL / API Gateway integration at `handler`. Both
`server.py` and `lambda_handler.py` are thin delivery layers over the same
`Agent.handle_request()` core logic — nothing agent-specific lives in either.

## Publishing to the marketplace

```python
run.publish(
    "https://my-agent.example.com/run",  # where this agent is reachable
    auth_type="bearer",                  # this agent's own runtime auth, if any
    auth_value="sk-...",                 # auto-prefixed to "Bearer sk-..."
    token="...",                         # your Levragent login token; falls back
                                          # to the LEVRAGENT_TOKEN env var
)
```

`name`, `description`, `domain`, `creator_name`, and the input/output
schemas are all pulled from the `@levragent.agent(...)` decoration — you
only pass connection details to `publish()`.

By default this creates the agent and immediately makes it live
(`go_live=True`). Pass `go_live=False` to leave it as a draft.

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```
