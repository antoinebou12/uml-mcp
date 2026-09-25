# Security Policy

We take security seriously. Please report vulnerabilities as described below; do not open public issues for security flaws.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.4.x   | :white_check_mark: |
| 1.3.x   | :white_check_mark: |
| < 1.3   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please follow these steps to report it:

1. **Do not disclose the vulnerability publicly** until it has been addressed by the maintainers.
2. **Report via GitHub:** Open a [Security Advisory](https://github.com/antoinebou12/uml-mcp/security/advisories/new) (preferred), or email the maintainers if you cannot use GitHub. Include:
   - The steps to reproduce the issue
   - The potential impact of the vulnerability
   - Any potential solutions or workarounds you're aware of

## Security Best Practices

When using this UML-MCP server in your environment, please follow these security best practices:

### Network Security
- Always run the service behind a secure proxy if exposing it to the internet
- Consider using HTTPS for any exposed endpoints
- Limit access to the server using IP restrictions or VPN when possible

### API Security
- Do not expose the MCP server directly to untrusted networks
- Use API keys or other authentication mechanisms when integrating with other services
- Validate all input coming from external sources

### Enterprise authentication
- For self-hosted HTTP deployments, enable `MCP_AUTH_MODE=jwt` or `entra-proxy` (Microsoft Entra ID / OAuth 2.1). See [docs/enterprise](docs/enterprise/README.md) and the [security model](docs/enterprise/security.md).
- Never forward client tokens to other services, and never put tokens in URLs.

### Server Environment
- Keep all dependencies up to date
- Run the service with minimal required permissions
- Use containerization to isolate the service from other applications

## Dependency Vulnerabilities

We use automated tools to scan for vulnerabilities in our dependencies and update them regularly. Users are encouraged to:

1. Regularly update to the latest version of this project
2. Report any known vulnerabilities in dependencies
3. Submit pull requests to update outdated or vulnerable dependencies

## Responsible Disclosure

We are committed to addressing security issues promptly. We will:

1. Acknowledge receipt of your vulnerability report within 48 hours
2. Provide a timeline for fixing the issue within 5 business days
3. Notify you when the vulnerability has been fixed
4. Acknowledge your contribution (unless you prefer to remain anonymous)

Thank you for helping keep this project secure!
