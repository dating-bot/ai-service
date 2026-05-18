set dotenv-load := true

manage := "uv run"

default:
    @just --choose

lint:
    {{ manage }} ruff format .
    {{ manage }} ruff check --fix .
    {{ manage }} mypy . --install-types --non-interactive --ignore-missing-imports
    {{ manage }} basedpyright .

run-tests:
    {{ manage }} pytest --verbose --no-header

migrate:
    {{ manage }} alembic upgrade head
