# Wolfpack AMP Backend

The AMP (Agent Management Platform) backend provides the operational control plane for Wolfpack AI agents.

## Development

```bash
uv sync --extra test --group dev
uv run pytest
```

The application requires PostgreSQL for normal runtime operation. Most tests use an in-memory database; the migration test is skipped unless `POSTGRES_TEST_URL` is configured.

## License

This package is distributed under the [Apache License 2.0](../../LICENSE).
