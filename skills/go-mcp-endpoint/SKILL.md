---
name: go-mcp-endpoint
description: 'Add a Streamable HTTP MCP endpoint (`/mcp`) to an existing Go service with the official github.com/modelcontextprotocol/go-sdk, so agents can call the service''s operations as MCP tools. Covers the stateless JSON setup, net/http and Fiber mounting, schema and error pitfalls, keeping answers small for agents, tests, live verification and registration in an MCP gateway. Use when the user says "add an MCP endpoint to this Go service", "expose the API as MCP tools", "make this service usable by agents over MCP", 「新增 /mcp」, 「讓 agent 透過 MCP 使用這個服務」, or is designing, testing or debugging such an endpoint.'
compatibility: Requires Go 1.25+ and github.com/modelcontextprotocol/go-sdk v1.x (written against v1.8.0).
---

# Go MCP endpoint (`/mcp`, Streamable HTTP)

Expose an existing Go service's operations as MCP tools on the same process and port. Every rule
below came from a real production failure.

## Shape

- **Transport layer only.** One package (e.g. `internal/transport/mcp`) that returns an
  `http.Handler`; each tool is one call into the existing service/app layer. No new business
  logic, so existing guards (read-only, auth, limits) apply unchanged.
- **Stateless + JSON**, not sessions + SSE: every tool is one request and one answer and there
  is nothing to push. POST only; GET/DELETE answer 405; no sticky sessions across replicas.
- **Same process, same port, path `/mcp`.** Mount before any static/UI catch-all route.
- **Tools 1:1 with service methods**, named `verb_noun` (`list_items`, `take_snapshot`).
  Skip composite or batch tools until someone asks.
- Use the project's domain vocabulary (CONTEXT.md) in tool names, descriptions and
  instructions, so agents speak the operators' language.

Before starting, settle with the user: who connects (local agents, CI, an MCP gateway), whether the
service's existing auth model covers `/mcp`, and which operations become tools.

## Handler template

```go
// Package mcp serves the app over the Model Context Protocol at /mcp.
// Stateless and JSON, never SSE: every tool is one request and one answer.
package mcp

func New(svc *app.Service) http.Handler {
	s := mcp.NewServer(&mcp.Implementation{Name: "myservice"},
		&mcp.ServerOptions{Instructions: instructions}) // 5-8 lines: workflow + vocabulary

	type getIn struct {
		ID   int64  `json:"id"`
		Name string `json:"name" jsonschema:"full name, such as team/item"` // tag = description
	}
	mcp.AddTool(s, &mcp.Tool{Name: "get_thing", Description: "..."},
		func(ctx context.Context, _ *mcp.CallToolRequest, in getIn) (*mcp.CallToolResult, any, error) {
			return result(svc.Get(ctx, in.ID, in.Name))
		})

	return mcp.NewStreamableHTTPHandler(func(*http.Request) *mcp.Server { return s },
		&mcp.StreamableHTTPOptions{Stateless: true, JSONResponse: true,
			MaxRequestBodyBytes: 8 << 20, // SDK default is 4 MiB; match router + ingress
			Logger:              slog.Default()})
}

// result returns one compact JSON text and no structuredContent; an error becomes a tool
// error (isError) and is logged, since no HTTP status shows it.
func result(v any, err error) (*mcp.CallToolResult, any, error) {
	if err == nil {
		var data []byte
		if data, err = json.Marshal(v); err == nil {
			return &mcp.CallToolResult{Content: []mcp.Content{&mcp.TextContent{Text: string(data)}}}, nil, nil
		}
	}
	slog.Warn("mcp tool failed", "err", err)
	return nil, nil, err
}
```

Mounting:

- net/http: `mux.Handle("/mcp", mcp.New(svc))`.
- Fiber v3: `app.All("/mcp", adaptor.HTTPHandler(mcp.New(svc)))` before `static`.

## Pitfalls (each one bit in production)

| Pitfall | Fix |
| --- | --- |
| Clients print every answer twice: SDK fills `content` **and** `structuredContent` (~3x tokens) | Return your own single `TextContent`, `out = nil` (template above) |
| Typed `Out` makes the SDK infer an output schema; Go nil maps/slices encode as `null` and fail it | Keep `Out` as `any` |
| Huge answers (a 560 KB snapshot) get truncated by the client and blow the agent's context | Main tool returns a summary (names, types, counts); add a drill-down tool to read one item. Mark truncation and totals explicitly |
| Body limit 4 MiB by default | `MaxRequestBodyBytes` aligned with router and ingress |
| SDK errors silently dropped | `Logger: slog.Default()`, plus log tool errors yourself |
| Domain "could not decide" confused with a broken call | A domain failure is a normal result (not `isError`); say in the tool description and instructions what it means ("failure is not a pass") so agents do not retry |

Know the schema rules (jsonschema-go, inferred from the input struct):

- Every struct gets `additionalProperties: false`, so unknown fields are rejected, like
  `DisallowUnknownFields`.
- Fields without `omitempty` are required, including **every field of a nested pointer struct**.
- The `jsonschema:"..."` tag is the field description.

Error mapping:

- A plain `error` from the handler becomes `isError: true` with the message.
- `*jsonrpc.Error` is a protocol error.
- Schema validation failures also arrive as `isError`.

DNS rebinding protection is on by default. It rejects a request only when the local address
is loopback and the Host header is not, so traffic through an ingress or a hub is unaffected.

## Tests

- Run the official client against the **real router mount**, so a wrong mount fails `Connect`:

  ```go
  ln, _ := net.Listen("tcp", "127.0.0.1:0")
  go srv.Serve(ln) // or fiber: app.Listener(ln, fiber.ListenConfig{DisableStartupMessage: true})
  cs, _ := mcp.NewClient(&mcp.Implementation{Name: "test"}, nil).
  	Connect(t.Context(), &mcp.StreamableClientTransport{Endpoint: "http://" + ln.Addr().String() + "/mcp"}, nil)
  res, _ := cs.CallTool(ctx, &mcp.CallToolParams{Name: "get_thing", Arguments: map[string]any{...}})
  ```

- Cover one happy-path workflow, then:
  - an unknown-entity error: `isError`;
  - a misspelt field: `isError`. Fill **every required field** in this call; otherwise it
    fails on the missing field and proves nothing about unknown fields;
  - `res.StructuredContent == nil && len(res.Content) == 1`;
  - that the summary carries counts, not contents.
- Check that `InitializeResult().Instructions` is non-empty.

## Verify live after deploy

```sh
u=https://<host>/mcp; h=(-sS -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream')
curl "${h[@]}" $u -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}'
curl "${h[@]}" $u -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
curl -s -o /dev/null -w '%{http_code}\n' $u   # GET -> 405
```

Then use a real client the way an agent would and look at what it receives: size, duplicates,
error text.

- A stateless server needs a client reconnect only when tools, descriptions or instructions
  change.
- Claude Code: `claude mcp add --transport http <name> https://<host>/mcp`.

## Register in an MCP gateway (if any)

When agents reach services through an aggregating MCP gateway/hub:

- Register the endpoint in **every** environment's server list (e.g. production and staging
  overlays). Use the in-cluster URL `http://<svc>.<ns>.svc.cluster.local/mcp` when both run in
  the same cluster, and check that the gateway's `NO_PROXY` covers `.svc.cluster.local`.
- Staging may point at the production service when the service has no staging deployment.
- Group/role restrictions:
  - Leave the server open only when it is read-only and already reachable without
    authentication, and add a one-line comment giving the reason.
  - Otherwise restrict it to the right groups. An open entry usually means anonymous callers
    can use its tools.
- If the gateway's tests do not load the deployed server lists, load each one with the
  gateway's own config loader before opening the change.

## Docs and gates

- Update README (endpoint URL, tool table, shortest workflow) and the developer guide (layout,
  API table, how MCP answers differ from REST).
- If the service has an "API stays under `/api/...`" rule or decision record, note `/mcp` as a
  deliberate exception.
- A new external contract plus a new dependency counts as a full-gate change: tests,
  simplification, a fresh review. Expect CI dependency/image scans to cover the SDK's transitive deps
  (`x/oauth2`, `golang-jwt`, `x/tools`, ...).
