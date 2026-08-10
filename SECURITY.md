# Security

## Trust boundary

Open-gpt is intentionally capable of giving ChatGPT the permissions of the local Open-gpt process. In full mode this includes arbitrary shell execution and whole-host file access. That behavior is the product's explicit purpose, not a sandbox escape.

Treat all of these as trusted computing base:

- the ChatGPT account and workspace allowed to select the plugin;
- the OpenAI tunnel and its runtime credential;
- this Open-gpt installation;
- every registered child MCP package and remote MCP endpoint;
- the operating-system account running Open-gpt.

Do not run full mode on a shared machine or expose the loopback gateway through an additional public reverse proxy.

## Safer deployment options

- Use `--scoped-root` instead of full mode when whole-host access is unnecessary.
- Run the Linux service as an unprivileged dedicated user.
- Keep the gateway on `127.0.0.1` and use the outbound OpenAI Secure MCP Tunnel.
- Pin npm, Python, container, and binary versions for child MCPs.
- Store secrets through `env:VARIABLE` or `file:/path` references instead of literal registry values.
- Stop or disable Open-gpt when remote access is not wanted.

## Credentials

The OpenAI tunnel runtime key is stored in macOS Keychain or a mode-`0600` Linux file. Dashboard output redacts tunnel IDs, child environment variables, and HTTP headers. Support logs and terminal output may still contain secrets produced by commands or child MCPs; review them before sharing.

## Reporting a vulnerability

Open a private GitHub security advisory in the repository. Do not include active API keys, tunnel IDs, authentication headers, or private command output in a public issue.
