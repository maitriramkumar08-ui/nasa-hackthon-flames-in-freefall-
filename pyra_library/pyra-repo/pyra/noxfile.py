"""Developer sessions: nox -s lint typecheck tests docs."""

import nox

nox.options.sessions = ["lint", "typecheck", "tests"]


@nox.session
def lint(session: nox.Session) -> None:
    session.install("ruff")
    session.run("ruff", "check", ".")
    session.run("ruff", "format", "--check", ".")


@nox.session
def typecheck(session: nox.Session) -> None:
    session.install("-e", ".[dev]")
    session.run("mypy", "src")


@nox.session
def tests(session: nox.Session) -> None:
    session.install("-e", ".[dev]")
    session.run("pytest")


@nox.session
def docs(session: nox.Session) -> None:
    session.install("mkdocs")
    session.run("mkdocs", "build", "--strict")
