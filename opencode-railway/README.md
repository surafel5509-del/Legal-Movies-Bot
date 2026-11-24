# OpenCode Railway runtime (v2)

This folder is an isolated Railway build context for the OpenCode service. It leaves the Legal-Movies-Bot application files at the repository root unchanged.

- OpenCode is pinned to v2.3.2 and its Linux x64 baseline archive is checked against the SHA-256 digest published in the official GitHub release.
- The upstream XavTo Railway template's MIT-licensed Caddy/entrypoint pattern is retained; see LICENSE.
- Global OpenCode configuration registers GitHub MCP using the existing `GITHUB_PERSONAL_ACCESS_TOKEN` Railway variable and loads the official Vercel plugin.
- GitHub MCP will only connect if the configured token is valid and has the required repository permissions.
- Vercel's plugin still requires a one-time OAuth sign-in from the OpenCode UI using `/mcps`.

Persistent application data stays under `/data`; the OpenCode global system configuration is installed under `/etc/opencode`.
