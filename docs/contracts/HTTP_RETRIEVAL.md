# HTTP retrieval

## Status

The shared parameter contract is implemented. The frozen request, selectable
transport, retrieval receipt, stage delivery, and verification models in this
document are approved for VIPER 0.1.

## Required claim

For each download input, VIPER verifies that the exact selected transport
received the frozen HTTP request and produced the file delivered to the exact
download-stage callable.

The completed path binds five identities:

```text
frozen HTTP request
        |
        v
exact transport implementation and parameters
        |
        v
retrieved file identity
        |
        v
exact download-stage callable
        |
        v
published artifacts
```

VIPER owns the request policy, credential resolution, destination path, file
hashing, receipt construction, and verification. The selected transport owns
the network transfer. Project tests establish the scientific correctness of
extraction and parsing code.

## Current gap

[`RemoteFileRef`](../../viper/protocol.py) stores a URL and a project-supplied
version. [`DownloadSpec`](../../viper/protocol.py) passes that declaration to a
project script. [`stage_worker.py`](../../viper/stage_worker.py) launches the
script with the stage-spec path. The script may ignore the declared URL.

[`ResolvedDownloadSpec`](../../viper/protocol.py) currently stores the authored
input and one timestamp. [`runner.py`](../../viper/runner.py) assigns the stage
start time to `retrieved_at`. The current verifier establishes artifact
identity after the stage runs while leaving the retrieval operation
unobserved.

The earlier draft also assigned transfer execution directly to one VIPER HTTP
client. The single-client boundary left the transport implementation implicit and
coupled the protocol to one client. It also treated one logical retrieval as
one HTTP exchange. A segmented downloader can issue several range requests to
produce one file, so the logical retrieval is the stable protocol unit.

## Contract models

### Parameterized download stage

Every stage inherits the same project-parameter contract:

```python
class ParameterizedSpec(BaseSpec):
    parameter_model: ParameterModelRef


class DownloadParams(ParameterSet):
    """Parameters consumed by one project-defined download procedure."""
```

`DownloadParams` holds extraction, pagination, archive, and parsing values.
The transport has its own parameter model because transfer settings belong to
the transport implementation.

### Frozen request and policy

```python
class EnvironmentSecretRef(ProtocolModel):
    kind: Literal["environment"] = "environment"
    variable: NonEmptyStr
    header: HttpHeaderName
    prefix: str = ""


class HttpRequestSpec(ProtocolModel):
    kind: Literal["http"] = "http"
    method: Literal["GET"] = "GET"
    url: HttpUrl
    headers: dict[HttpHeaderName, NonEmptyStr] = Field(default_factory=dict)
    version: NonEmptyStr
    credentials: EnvironmentSecretRef | None = None


class HttpRetrievalPolicy(ProtocolModel):
    allowed_schemes: frozenset[Literal["http", "https"]] = Field(min_length=1)
    allowed_hosts: frozenset[NonEmptyStr] = Field(min_length=1)
    allowed_ports: frozenset[
        Annotated[int, Field(ge=1, le=65535)]
    ] = Field(min_length=1)
    accepted_statuses: frozenset[
        Annotated[int, Field(ge=100, le=599)]
    ] = frozenset({200})
    max_redirects: int = Field(ge=0)
    max_retrievals: int = Field(gt=0)
    max_body_bytes: int = Field(gt=0)
    timeout_seconds: float = Field(gt=0, allow_inf_nan=False)
```

The authoring API may accept a URL template, path values, and query values. The
frozen stage spec stores the expanded URL. URI normalization follows
[RFC 3986, Section 6](https://www.rfc-editor.org/rfc/rfc3986.html#section-6).

`headers` contains public fields that select or describe the requested
representation. VIPER rejects literal authorization credentials, cookies, and
proxy credentials. `EnvironmentSecretRef.variable` names an environment
variable available to the controlled child. `header` selects the request field
that receives the secret, and `prefix` supplies public text such as `Bearer `.
The secret value stays outside the frozen plan and resolved result.

`allowed_hosts` contains normalized, lower-case host names and uses exact
matching. `HttpRetrievalPolicy` governs each initial request, follow-up request,
and redirect target. `max_retrievals` applies to the complete stage;
`max_body_bytes` and `timeout_seconds` apply to each logical retrieval.

HTTP defines a request through its method, target, and fields, and a response
through its status, fields, and content. The request model follows those
message components from
[RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html#section-3.4).

### Transport selection

VIPER supplies one built-in HTTPX transport. A project may select an exact
decorated transport callable for a different transfer engine.

```python
class HttpTransportParams(ParameterSet):
    """Parameters consumed by one HTTP transport implementation."""


class HttpTransportImplementationRef(ProtocolModel):
    path: PythonRepoRelPath
    symbol: PythonSymbol
    sha256: SHA256
    bytes: int = Field(gt=0)


class BuiltinHttpTransportSpec(ProtocolModel):
    kind: Literal["builtin"] = "builtin"
    transport_id: Literal["httpx"] = "httpx"


class ProjectHttpTransportSpec(ProtocolModel):
    kind: Literal["project"] = "project"
    transport_id: HumanId
    implementation: HttpTransportImplementationRef
    parameter_model: ParameterModelRef
    params: HttpTransportParams


HttpTransportSpec = Annotated[
    BuiltinHttpTransportSpec | ProjectHttpTransportSpec,
    Field(discriminator="kind"),
]
```

For the built-in transport, `ProcessStartupReceipt` and the effective Python
environment identify the installed VIPER and HTTPX versions. For a project
transport, `RunSpec.source`, `HttpTransportImplementationRef`, and
`ParameterModelRef` identify the exact callable and validator bytes.

Requests exposes transport adapters for client-specific behavior. HTTPX
exposes custom transports that send one request and return one response. The
VIPER interface applies the same separation at the provenance boundary:
[Requests transport adapters](https://requests.readthedocs.io/en/stable/user/advanced/#transport-adapters)
and
[HTTPX custom transports](https://www.python-httpx.org/advanced/transports/).

The download stage selects one transport:

```python
class DownloadSpec(ParameterizedSpec):
    kind: Literal["download"] = "download"
    inputs: dict[InputName, HttpRequestSpec] = Field(min_length=1)
    transport: HttpTransportSpec
    policy: HttpRetrievalPolicy
    params: DownloadParams
```

One transport governs every retrieval initiated by that stage. A plan that
requires different transports uses separate download stages, preserving one
transport identity per stage result.

### Project transport interface

A project transport is an ordinary decorated top-level callable:

```python
class Aria2TransportParams(HttpTransportParams):
    connections: int = Field(gt=0)
    split: int = Field(gt=0)
    continue_partial: bool = True


@viper.http_transport(
    transport_id="aria2c",
    parameter_model=Aria2TransportParams,
)
def aria2c_transport(
    context: HttpTransportContext[Aria2TransportParams],
) -> HttpTransportResult:
    ...
```

The decorator supplies authoring metadata. Freezing resolves the callable and
parameter class into `ProjectHttpTransportSpec`.

The runner constructs one context for each logical retrieval:

```python
TransportParamsT = TypeVar("TransportParamsT", bound=HttpTransportParams)


class RuntimeHttpCredential(ProtocolModel):
    header: HttpHeaderName
    prefix: str
    value: SecretStr


class HttpTransportContext(ProtocolModel, Generic[TransportParamsT]):
    schema_version: Literal[1] = 1
    request: HttpRequestSpec
    credential: RuntimeHttpCredential | None
    workspace: Path
    destination: Path
    policy: HttpRetrievalPolicy
    params: TransportParamsT


class ObservedHttpResponse(ProtocolModel):
    response_url: HttpUrl
    status: int = Field(ge=100, le=599)
    response_headers: dict[HttpHeaderName, str]


class ExternalExecutableObservation(ProtocolModel):
    name: HumanId
    path: Path
    version: NonEmptyStr


class HttpTransportResult(ProtocolModel):
    body: Path
    response: ObservedHttpResponse | None = None
    external_executables: tuple[ExternalExecutableObservation, ...] = ()
```

`HttpRequestSpec.headers` contains the public headers.
`RuntimeHttpCredential.value` contains the resolved secret as `SecretStr`. The
transport combines them only when it sends the request. VIPER redacts the
secret from persisted output. The runner assigns a dedicated retrieval
`workspace` inside the attempt workspace. `destination` is the exact body path
within that directory. A transport such as `aria2c` may place temporary
transfer files beside the destination. The transport returns only after the
completed body exists at `destination`.

`ObservedHttpResponse` is present when the selected transport exposes the
terminal HTTP response. The built-in HTTPX transport must provide it. A file
transfer engine may return only the completed body. The transport-independent
claim rests on the frozen request, exact transport invocation, and final file
identity.

VIPER persists only `content-type`, `content-encoding`, `content-length`,
`etag`, `last-modified`, `digest`, and `content-digest` from the terminal
response. The runner rejects a returned response whose status falls outside
`HttpRetrievalPolicy.accepted_statuses`. A transport that omits `response` must
pass the same accepted-status behavior in the transport conformance suite.

An external executable observation names each binary used by the decorated
adapter. The runner reads the executable at `path`, computes its SHA-256 and
byte count, and persists the observed version. This captures an `aria2c`
adapter's actual transfer engine in addition to the Python wrapper.

Aria2 supports segmented HTTP transfers, multiple connections, partial-transfer
continuation, and explicit checksum validation:
[aria2 documentation](https://aria2.github.io/manual/en/html/aria2c.html).

### Resolved retrieval

```python
class ResolvedExternalExecutable(ProtocolModel):
    name: HumanId
    path: Path
    version: NonEmptyStr
    sha256: SHA256
    bytes: int = Field(gt=0)


class ResolvedHttpTransport(ProtocolModel):
    spec: HttpTransportSpec
    external_executables: tuple[ResolvedExternalExecutable, ...] = ()


class ResolvedHttpRetrieval(ProtocolModel):
    input_name: InputName
    retrieval_index: int = Field(ge=0)
    cause: Literal["initial", "follow_up"]
    request: HttpRequestSpec
    transport: ResolvedHttpTransport
    response: ObservedHttpResponse | None
    body: ResolvedFileRef
    started_at: AwareDatetime
    completed_at: AwareDatetime


class ResolvedDownloadSpec(ResolvedBaseSpec):
    spec: DownloadSpec
    retrievals: tuple[ResolvedHttpRetrieval, ...] = Field(min_length=1)
```

`retrieval_index` starts at `0` for each input and records logical retrieval
order. Redirects and segmented range requests remain internal operations of
one transport invocation. A pagination request or another project-requested
URL creates a new logical retrieval with cause `follow_up`.

`body` identifies the completed file through its storage location, SHA-256,
and byte count. `response` preserves the terminal HTTP status, effective URL,
and allowlisted representation headers when the transport exposes them.

The initial retrieval for each input satisfies:

```text
ResolvedHttpRetrieval.input_name
-> DownloadSpec.inputs[input_name]

ResolvedHttpRetrieval.retrieval_index
== 0

ResolvedHttpRetrieval.cause
== initial

ResolvedHttpRetrieval.request
== DownloadSpec.inputs[input_name]

ResolvedHttpRetrieval.transport.spec
== DownloadSpec.transport
```

## Execution

### Transport invocation

The runner performs this sequence for every logical retrieval:

```text
validate request against HttpRetrievalPolicy
        |
        v
resolve runtime credentials
        |
        v
load the selected built-in or project transport
        |
        v
construct HttpTransportContext
        |
        v
invoke the exact transport callable
        |
        v
verify the returned path and external executables
        |
        v
hash and store the completed body
        |
        v
write ResolvedHttpRetrieval
```

The runner owns the timestamps surrounding transport invocation. It requires
`HttpTransportResult.body` to equal the assigned destination, rejects symlinks
and path escape, checks the terminal response when supplied, enforces the
body-size and elapsed-time limits, and stores the completed file before
returning a handle to project code. A successful transport invocation returns
`HttpTransportResult`; a failed invocation raises the typed transport error
defined by `viper.http`.

### Download-stage interface

The client-neutral stage interface is:

```python
class HttpRetrievalHandle(ProtocolModel):
    retrieval_index: int = Field(ge=0)
    cause: Literal["initial", "follow_up"]
    response: ObservedHttpResponse | None
    body: Path


class ControlledHttpRetriever(Protocol):
    def get(
        self,
        input_name: InputName,
        url: HttpUrl,
        *,
        headers: Mapping[HttpHeaderName, str] | None = None,
    ) -> HttpRetrievalHandle:
        ...


class DownloadContext(StageContext[DownloadParams]):
    retrievals: dict[InputName, tuple[HttpRetrievalHandle, ...]]
    http: ControlledHttpRetriever
```

Each tuple follows `retrieval_index` order. Each `body` path contains the bytes
identified by the corresponding `ResolvedHttpRetrieval.body`.
`ControlledHttpRetriever.get()` accepts an input already declared by the stage,
inherits its credential reference, applies `DownloadSpec.transport` and
`DownloadSpec.policy`, and appends the completed retrieval to that input's
sequence.

### Pagination and scraping

A project download callable may request additional pages through
`DownloadContext.http`. Each call creates one `ResolvedHttpRetrieval` with the
same input name and the next contiguous index. Frozen `DownloadParams` define
pagination values, selectors, and termination rules. `HttpRetrievalPolicy`
limits permitted targets, retrieval count, body size, and elapsed time.

## Persisted evidence

The resolved download stage contains every logical retrieval used by the stage
callable. Each retrieval binds the frozen request, selected transport,
effective external executable identity, final body identity, and runner-owned
timestamps.

Each retrieved body uses this canonical snapshot path:

```text
experiments/<experiment_id>/runs/<variant_id>/<run_id>/
└── stages/<stage_id>/retrievals/<input_name>/<retrieval_index>/body
```

The stage invocation receipt binds the resulting `DownloadContext` to the
exact download-stage callable. The stage snapshot stores the resolved download
specification and retrieved bodies together with the declared artifacts.

## Verification

The verifier performs these named checks:

| Check | Rule |
|---|---|
| `http.input` | Every retrieval names one key in `DownloadSpec.inputs`. |
| `http.request` | Retrieval `0` for each input equals `DownloadSpec.inputs[input_name]`. |
| `http.policy` | Every initial and follow-up request satisfies `DownloadSpec.policy`. |
| `http.credentials` | The runner resolves the named secret, injects it into the selected header, and redacts its value from persisted evidence. |
| `http.transport.identity` | The built-in transport matches the effective installed environment, or the project transport callable and parameter model match their frozen identities. |
| `http.transport.parameters` | Project transport parameters validate through the selected parameter class and equal the frozen mapping. |
| `http.transport.executable` | Every declared external executable matches its observed path, version, SHA-256, and byte count. |
| `http.response` | A recorded terminal response uses an accepted status and contains only the permitted persisted fields. |
| `http.content` | Retrieved bytes match `body.sha256` and `body.bytes`. |
| `http.order` | Retrieval indices are unique, contiguous, and ordered within each input. |
| `http.delivery` | Each context handle matches one resolved retrieval and its body path contains the verified bytes. |
| `parameter_model.identity` | Download parameter-model bytes match the frozen source identity. |
| `parameter_model.validation` | Frozen download parameters validate through the selected class. |
| `stage.source` | The executed download callable matches the frozen source identity. |
| `artifact.files` | Published artifact bytes match the resolved artifact identities. |

These checks establish that the identified transport callable received the
frozen request, produced the identified file, and supplied that file to the
identified download-stage callable.

VIPER 0.1 trusts the selected project transport and download-stage source.
Future network confinement will restrict undeclared outbound paths and support
a complete network-input claim.

## Propagation

| Surface | Required change |
|---|---|
| Protocol | Add the request, policy, transport, retrieval, and external-executable models. |
| Authoring | Expand URL templates, freeze the final request and selected transport, resolve decorated transport metadata, and reject literal credentials. |
| Variant binding | Include download-stage and project-transport parameter mappings. |
| Preflight | Validate request policy, callable identities, parameter identities, secret availability, retrieval limits, and required external executables. |
| Runner | Invoke the selected transport, constrain its destination, hash its output, and persist each logical retrieval before stage invocation. |
| Stage interface | Expose verified retrieval handles and the controlled follow-up interface through `DownloadContext`. |
| Resolved result | Publish the ordered retrieval sequence, transport evidence, external-tool identities, and body identities. |
| Verifier | Apply the named HTTP, transport, delivery, source, and artifact checks. |
| Public API | Export `http_transport`, transport contexts, transport results, and transport parameter bases. |
| Tests | Apply the transport conformance suite to the built-in transport and one decorated project transport. |

## Acceptance case

The built-in acceptance case freezes one HTTPX retrieval from a local test
server. The server returns one redirect followed by status `200`, content type
`application/gzip`, and fixed bytes. The runner records one logical retrieval,
stores the completed body, constructs `DownloadContext`, and invokes the exact
download callable. The test checks the frozen request, built-in transport
identity, final body digest, byte count, stage invocation receipt, extracted
artifact identity, and terminal run verification.

The project-transport acceptance case decorates a transport with typed
parameters, freezes its implementation identity, and retrieves the same bytes
from a range-capable local server. The test checks transport-parameter delivery,
external-executable identity when one is used, and the same final body digest.

The conformance suite also covers a disallowed host, missing secret, timeout,
oversized body, returned path escape, missing external executable, modified
transport source, and same-length body tampering. Each case must fail through
its named preflight, runtime, or verifier rule.

## Implementation order

1. Add frozen request, retrieval-policy, transport, and resolved-retrieval
   models.
2. Add the transport decorator, project-transport parameter validation, and
   source-identity checks.
3. Implement the built-in HTTPX transport and runner-owned body storage.
4. Add `DownloadContext` and route every project follow-up through the selected
   transport.
5. Add external-executable observation and verification for adapters such as
   `aria2c`.
6. Add verifier rules and the transport conformance suite.
