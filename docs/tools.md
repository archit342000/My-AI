# Tools and MCP services

How to add a tool the model can call, or a new external service. Component details are in `backend/tools/README.md`.

## Tool types

- **Pure tool:** a plain function that returns a result. Registered by a `ToolSpec` (`backend/tools/spec.py`).
- **Agent tool:** starts an autonomous sub-agent (`backend/tools/agents/<name>/`) through `AgentHandler`; its steps are stored in `sub_agent_messages`.
- **MCP-backed tool:** the function calls a separate container through `backend/mcp_client.py`
  (`tavily_mcp` search, `playwright_mcp` browsing, `code_runner_mcp` code execution).

## Adding a tool

1. Write the function (async if it does I/O) in the right module under `backend/tools/` or `backend/tools/implementations/`.
   Signature takes the model's arguments, `chat_id` where needed, and `**kwargs`. A tool that reads or writes user data (preferences, skills) declares `user_id`: the server injects the chat owner through `system_ctx`, overriding any value the model sends, and the tool returns an error when it is missing. Return a string (or JSON-serializable value).
2. Define a `ToolSpec` in `backend/tools/catalog/<domain>.py`: `name`, `description`, JSON-schema `parameters`,
   `implementation` (dotted path), `tool_type`, `scopes` and, if mode-gated, `requires_mode`. Set `admin_only=True` when the tool reaches host-wide state (git, package installs): it is then offered to and runnable by admin-owned chats only.
3. Add the spec list to `ALL_TOOL_SPECS` in `backend/tools/catalog/__init__.py` if you created a new catalog module.
4. Add usage instructions as a prompt template `backend/prompts/templates/directives/<tool_name>.txt` (loaded as `spec.directives`).
5. Tests: the function (`tests/test_<module>.py`), and the catalog completeness test in `backend/tools/catalog/tests/` must pass.
6. Update the component README only if the tool's role or constraints are new (`docs/standards/docs.md`).

## Rules for tools

- Return errors as text beginning with `Error` or `Failed`; the tool handler treats those as failed calls (`backend/tools/safety.py`).
  Raise only for programmer errors.
- Bound output size (character caps in `backend/config.py`, for example `MAX_CHARS_VISIT_PAGE`) so one result cannot fill the context.
- All network calls go through `backend/error_handling.py` with an explicit timeout.
- Respect scopes: a tool is offered only to the agent contexts listed in `scopes`.
- Anything that executes code, touches the network for user-controlled URLs, or writes files follows `docs/standards/security.md`
  (path checks, SSRF check, allow-lists).

## Adding an MCP service

1. New top-level directory with `server.py`, `requirements.txt`, `README.md` and `tests/`.
2. Dockerfile in `docker/` (pinned base, non-root user) and a service in `docker/docker-compose.yml` on `secure-internal` (or on `runner-net` only, for a sandbox that must not reach the internet or databases),
   with an API key in Docker secrets and resource limits if it runs untrusted work (`docs/standards/docker.md`).
3. A client in `backend/mcp_client.py` and tools that call it. Timeouts use `TIMEOUT_MCP_TOOL_CALL`.
4. Document the boundary in `docs/architecture.md`.
