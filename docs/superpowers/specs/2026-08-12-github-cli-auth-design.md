# GitHub CLI Authentication Design

## Goal

Make one interactive `ethergpt-github-auth` setup configure every GitHub path
used by a developer host:

- the GitHub MCP exposed through EtherGPT;
- HTTPS Git operations through the existing credential helper; and
- the GitHub CLI (`gh`) used by terminal agents.

After setup, `gh auth status --hostname github.com`, GitHub MCP probing, and
private HTTPS Git operations must all use the same user-supplied token.

## Current gap

The helper stores the token in EtherGPT's protected secret file, enables and
probes the GitHub MCP, and leaves Git configured to use the protected token
file. It does not populate GitHub CLI's own authentication store. A terminal
agent that treats `gh auth status` as the only source of truth therefore reports
that GitHub is unavailable even while the MCP and Git credential helper work.

## Selected design

Keep the protected EtherGPT token file as the input source. After the MCP probe
succeeds, detect whether `gh` is installed. When it is available, pass the token
to `gh auth login --hostname github.com --git-protocol https --with-token` on
standard input. The token must never be placed in a command argument, log, or
shell history.

`gh` may store the credential in the operating system credential store or fall
back to its root/user-only configuration file, matching GitHub CLI's documented
behavior. The existing EtherGPT token file remains mode `0600`; its parent
secret directory remains mode `0700`.

If `gh` is not installed, setup continues successfully and reports that only
GitHub CLI integration was skipped. MCP and Git authentication must not be
disabled merely because an optional CLI is absent.

## Clear behavior

`ethergpt-github-auth --clear` will:

1. empty the protected EtherGPT token file;
2. disable the GitHub MCP; and
3. remove the local `github.com` GitHub CLI authentication when `gh` is present
   and an account is configured.

GitHub CLI logout removes local authentication configuration; it does not revoke
the PAT on GitHub. Revocation remains an explicit action in GitHub settings.

## Error handling

- An MCP probe failure keeps the existing behavior: disable the MCP and return a
  failure.
- A GitHub CLI login failure returns a failure after reporting which integration
  failed. The protected token and working MCP are kept so the user can retry
  without losing access.
- Token contents are never printed.
- Commands are non-interactive after the initial hidden token prompt.

## Tests

The helper test will use a fake `gh` executable and verify that:

- setup invokes `gh auth login` with the intended hostname, protocol, and
  standard-input mode;
- the token arrives on standard input rather than in command arguments;
- setup still succeeds when `gh` is absent;
- `--clear` logs out an existing GitHub CLI account without prompting; and
- existing MCP enable, probe-failure rollback, file-permission, and credential
  helper tests continue to pass.

Operational verification on macOS and the Babil root account will run
`gh auth status`, an authenticated `gh api user` request, the GitHub MCP probe,
and a secret-permission check without displaying the token.
