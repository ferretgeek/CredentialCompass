# Contributing

Thank you for helping Credential Compass stay quiet, useful, and safe.

1. Use synthetic identities under `example.com`, `example.net`, or `example.org` only.
2. Never attach real credentials, account files, upstream response bodies, management URLs, deployment details, screenshots, or logs.
3. Keep the browser boundary data-minimal. New network targets, secret persistence, exports, irreversible actions, or relaxed limits are out of scope.
4. Update both Chinese and English documentation when behavior changes.
5. Run:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
ruff check .
ruff format --check .
python -m compileall -q src tests
```

Security reports belong in GitHub Private vulnerability reporting, not a public issue.
