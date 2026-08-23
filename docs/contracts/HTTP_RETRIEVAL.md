# HTTP retrieval

## Status

The shared parameter contract is implemented. The HTTP request, execution,
receipt, and verification models in this document define the next protocol
increment.

## Required claim

For each download stage, VIPER must identify the HTTP request selected by the
frozen plan, execute that request through the controlled retrieval client,
record the received response, and deliver the verified response bytes to the
selected stage implementation.

The stage result must bind four identities:

```text
frozen request
      |
      v
HTTP response bytes
      |
      v
exact stage implementation
      |
      v
published artifacts
```

The verifier checks each link represented by a protocol field. Project tests
establish the scientific correctness of extraction and parsing code.

## Current gap

[`RemoteFileRef`](../../viper/protocol.py) stores a URL and a project-supplied
version. [`DownloadSpec`](../../viper/protocol.py) passes that declaration to a
project script. [`stage_worker.py`](../../viper/stage_worker.py) launches the
script with the stage-spec path. The script may ignore the declared URL.

[`ResolvedDownloadSpec`](../../viper/protocol.py) currently stores the authored
input and one timestamp. Those are the protocol's complete download-retrieval
evidence. [`runner.py`](../../viper/runner.py) assigns the stage start time to
`retrieved_at`, leaving the actual HTTP exchange unobserved.

The current verifier establishes artifact identity after a download stage runs.
The HTTP response identity remains unverified.

## Planned models

### Parameterized stage

Every stage inherits the same project-parameter contract:

```python
class ParameterizedSpec(BaseSpec):
    parameter_model: ParameterModelRef


class DownloadParams(ParameterSet):
    """Parameters consumed by one project-defined download procedure."""


class DownloadSpec(ParameterizedSpec):
    kind: Literal["download"] = "download"
    inputs: dict[InputName, HttpRequestSpec] = Field(min_length=1)
    params: DownloadParams
```

`DownloadParams` holds project-defined extraction, pagination, archive, and
parsing values. `HttpRequestSpec` holds the network request that VIPER executes.

### Frozen request

```python
class EnvironmentSecretRef(ProtocolModel):
    kind: Literal["environment"] = "environment"
    variable: NonEmptyStr


class HttpRequestSpec(ProtocolModel):
    kind: Literal["http"] = "http"
    method: Literal["GET"] = "GET"
    url: HttpUrl
    headers: dict[HttpHeaderName, NonEmptyStr] = Field(default_factory=dict)
    version: NonEmptyStr
    credentials: EnvironmentSecretRef | None = None
```

The authoring API may accept a URL template, path values, and query values. The
frozen stage spec stores the expanded URL. URI normalization follows the
equivalence rules in [RFC 3986, Section 6](https://www.rfc-editor.org/rfc/rfc3986.html#section-6).

`headers` contains fields that select or describe the requested
representation. VIPER rejects literal authorization credentials, cookies, and
proxy credentials. `EnvironmentSecretRef.variable` names an environment
variable available to the controlled retrieval process. Its value stays
outside the run plan and resolved result.

HTTP defines a request through its method, target, and fields, and defines a
response through its status, fields, and content. The model follows those
message components from [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html#section-3.4).

### Resolved exchange

```python
class ResolvedHttpExchange(ProtocolModel):
    input_name: InputName
    exchange_index: int = Field(ge=0)
    cause: Literal["initial", "redirect", "follow_up"]
    request: HttpRequestSpec
    response_url: HttpUrl
    status: int = Field(ge=100, le=599)
    response_headers: dict[HttpHeaderName, str]
    body: ResolvedFileRef
    completed_at: AwareDatetime


class ResolvedDownloadSpec(ResolvedBaseSpec):
    spec: DownloadSpec
    exchanges: tuple[ResolvedHttpExchange, ...] = Field(min_length=1)
```

`input_name` joins each exchange to one key in `DownloadSpec.inputs`.
`exchange_index` starts at `0` for each input and records the request order for
redirects, pagination, and follow-up retrievals.

`response_headers` records the allowlisted fields needed to interpret or
validate the representation, including content type, content encoding, entity
tag, last-modified time, and content length when supplied. RFC 9110 defines
content as representation data interpreted through its representation
metadata.

`body` identifies the immutable response file through its storage location,
SHA-256 digest, and byte count. The runner retrieves each file when it
constructs the ordered response handles for that input.

The initial exchange for each input satisfies:

```text
ResolvedHttpExchange.input_name
-> DownloadSpec.inputs[input_name]

ResolvedHttpExchange.exchange_index
== 0

ResolvedHttpExchange.cause
== initial

ResolvedHttpExchange.request
== DownloadSpec.inputs[input_name]
```

## Execution

### Static retrieval

The runner performs this sequence for each frozen request:

```text
validate request against network policy
      |
      v
resolve runtime credentials
      |
      v
send request through the VIPER HTTP client
      |
      v
store response bytes and ResolvedHttpExchange
      |
      v
construct the download stage context
      |
      v
invoke the exact project implementation
      |
      v
publish declared artifacts
```

The download context extends `StageContext` with:

```python
class HttpResponseHandle(ProtocolModel):
    exchange_index: int = Field(ge=0)
    cause: Literal["initial", "redirect", "follow_up"]
    response_url: HttpUrl
    status: int = Field(ge=100, le=599)
    response_headers: dict[HttpHeaderName, str]
    body: Path


class ControlledHttpClient(Protocol):
    def get(
        self,
        input_name: InputName,
        url: HttpUrl,
        *,
        headers: Mapping[HttpHeaderName, str] | None = None,
    ) -> HttpResponseHandle:
        ...


class DownloadContext(StageContext[DownloadParams]):
    responses: dict[InputName, tuple[HttpResponseHandle, ...]]
    http: ControlledHttpClient
```

Each tuple follows `exchange_index` order. Each `body` path contains the bytes
identified by the corresponding `ResolvedHttpExchange.body`. Project code
receives `DownloadParams` as its validated project-defined type.
`ControlledHttpClient.get()` accepts an input name already declared by the
stage, inherits that input's version and credential reference, applies the
network policy, and appends the resulting exchange to that input's sequence.
The final accepted response for one input is the last handle in its tuple.

### Pagination and scraping

A project-defined download procedure may request additional pages through
`DownloadContext.http`. Each request produces one `ResolvedHttpExchange` with
the same `input_name` and the next contiguous `exchange_index`. The frozen
parameters define pagination limits, selectors, and termination rules. The
execution policy limits permitted schemes, hosts, ports, request count,
response size, and elapsed time.

The resolved exchange sequence preserves every realized request target and
response identity used by the stage invocation.

## Verification

The verifier performs these named checks:

| Check | Rule |
|---|---|
| `http.input` | Every exchange names one key in `DownloadSpec.inputs`. |
| `http.request` | Exchange `0` for each input equals `DownloadSpec.inputs[input_name]`. |
| `http.policy` | Every realized target satisfies the stage network policy. |
| `http.status` | Every recorded status satisfies the declared success policy. |
| `http.content` | The bytes retrieved through `body.stored_at` match `body.sha256` and `body.bytes`. |
| `http.order` | Exchange indices are unique, contiguous, and ordered within each input. |
| `http.cause` | Exchange `0` is initial; each redirect follows the prior response's redirect target; each follow-up was issued through `DownloadContext.http`. |
| `http.delivery` | Each response handle matches one exchange for its input, in exchange-index order, and its body path contains the verified body bytes. |
| `parameter_model.identity` | Download parameter-model bytes match the frozen source identity. |
| `parameter_model.validation` | Frozen download parameters validate through the selected class. |
| `stage.source` | The executed download implementation matches the frozen source identity. |
| `artifact.files` | Published artifact bytes match the resolved artifact identities. |

These checks support a precise 0.1 provenance statement: the identified stage
implementation received the identified response files from VIPER's controlled
client and produced the identified artifact files during one recorded
invocation.

VIPER 0.1 trusts project source to use the delivered response handles for
network input. The future confinement contract will restrict direct outbound
network access and support a complete network-input claim.

## Propagation

| Surface | Required change |
|---|---|
| Protocol | Add `HttpRequestSpec`, `EnvironmentSecretRef`, `ResolvedHttpExchange`, and the revised `ResolvedDownloadSpec`. |
| Authoring | Expand URL templates; freeze the final request; reject literal credentials. |
| Variant binding | Include `DownloadVariantStageParams` in the selected stage-parameter mapping. |
| Preflight | Validate request policy, parameter identity, secret availability, and retrieval limits. |
| Runner | Execute HTTP through the controlled client and store response bodies before stage invocation. |
| Stage interface | Extend `StageContext` as `DownloadContext`, carrying typed `DownloadParams` and verified response handles. |
| Trust boundary | Treat project source as trusted in 0.1 and record every request made through the controlled client. |
| Resolved result | Publish the complete ordered exchange sequence and response identities. |
| Verifier | Apply the named HTTP, parameter, source, and artifact checks. |
| Tests | Exercise one static request, one redirect, one paginated source, one secret reference, and each rejection rule. |

## Acceptance case

The first executable acceptance case freezes this request:

```yaml
kind: download
inputs:
  archive:
    kind: http
    method: GET
    url: https://example.test/data/v1/archive.tar.gz?format=raw
    headers:
      Accept: application/gzip
    version: v1
```

The local test server returns status `200`, content type
`application/gzip`, and fixed response bytes. The project implementation
extracts one declared member. The test then checks the resolved URL, status,
response digest, response byte count, extracted artifact digest, and terminal
run verification. A second case changes one response byte while preserving the
response length; verification must fail on SHA-256.

## Implementation order

1. Keep the implemented `ParameterizedSpec` inheritance and download parameter
   validation.
2. Add the frozen request and resolved exchange models.
3. Add the controlled client and immutable response storage.
4. Add `DownloadContext` and route project download code through it.
5. Enforce the network policy in preflight and the execution backend.
6. Add verifier rules and executable acceptance cases.
