# Contributing to Wolfpack AI

Thanks for contributing to Wolfpack AI. Contributions are accepted through GitHub Pull Requests (PRs).

## Before you start

Open an issue before beginning a large change. Explain the problem, the proposed approach, and any API (Application Programming Interface) impact. This avoids duplicate work and gives maintainers a chance to confirm the direction.

For vulnerabilities, do not open a public issue. Follow [SECURITY.md](SECURITY.md).

## Development setup

The repository has three applications:

- `framework/`: the Python package published as `wolfpackai`.
- `control-plane/`: the AMP (Agent Management Platform) backend and frontend.
- `website/`: documentation website.

For framework changes:

```bash
cd framework
uv sync --extra test --group dev
uv run pytest
```

For AMP backend changes:

```bash
cd control-plane/backend
uv sync --extra test --group dev
uv run pytest
```

For frontend changes:

```bash
cd control-plane/frontend
npm ci
npm run lint
npm run build
```

For website changes:

```bash
cd website
npm ci
npm run build
```

## Pull Request process

1. Fork the repository and create a branch from `main`.
2. Keep the change focused and include tests for behavior changes.
3. Run the relevant commands listed above.
4. Open a Pull Request against `main` and complete the template.
5. A maintainer reviews the change before merging it.

Do not commit generated build output, credentials, tokens, private keys, or local environment files.

## Contribution terms

By submitting a contribution, you confirm that you have the right to submit it and agree to license it under the [Apache License 2.0](LICENSE). This is the inbound equals outbound model: contributions use the same license as the project.

## Code and documentation

- Follow existing code style and naming conventions.
- Keep public behavior and API changes documented.
- Use clear commit and Pull Request descriptions.
- Keep documentation accurate and avoid exposing real credentials, customer data, or personally identifiable information.
