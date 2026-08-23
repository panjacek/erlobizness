---
name: qa-review
description: Perform comprehensive quality assurance reviews on code changes, focusing on correctness, maintainability, and adherence to project standards.
---

## Guidelines
- **KISS Principle**: Ensure all solutions and suggestions follow "Keep It Stupid Simple" principles.
- **Verification**: Always run `make lint` and `make test` to verify changes. Use `make format` if needed.
- **Lint Compliance**: Ensure zero errors in **Ruff** (PY) and **Biome** (JS).
- **Testing**: Confirm 100% pass rate in **pytest** and **vitest**.
- **Succinctness**: Provide direct, actionable feedback without fluff.

## Review Checklist
1.  Does the code solve the problem simply? (KISS)
2.  Do `make lint` and `make test` pass without errors?
3.  Is the code easy to read and maintain?
4.  Are there sufficient tests for new logic?
5.  Is the implementation free of unnecessary complexity?