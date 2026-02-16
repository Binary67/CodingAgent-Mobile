# Codex Coding Contracts

These contracts are mandatory for all code changes in this repository.

## 1) Readability and Maintainability First
- Prioritize clear, maintainable code so other developers can quickly understand, review, and safely modify it.
- Prefer straightforward solutions over clever or overly condensed implementations.

## 2) Use Descriptive Names
- Use explicit, intention-revealing names for variables, functions, classes, parameters, and constants.
- Avoid vague names (`a`, `tmp`, `data`, `obj`) unless the scope is very small and obvious.

## 3) Avoid Long Sequential Conditionals
- Avoid long `if/elif/else` (or equivalent) chains when a clearer structure exists.
- Prefer lookup tables/maps, polymorphism, strategy objects, or `match/switch` when they improve clarity.

## 4) Reduce Nested Logic
- Keep nesting shallow.
- Use guard clauses and early returns to handle invalid or edge conditions first.

## 5) Keep Functions Focused
- Split large functions/methods into smaller units with a single responsibility.
- Extract validation, transformation, side effects, and formatting into clearly named helpers where appropriate.

## 6) Document Non-Obvious Intent
- Add concise comments/docstrings for assumptions, invariants, and reasoning that is not obvious from code alone.
- Do not add comments that restate what the code already clearly expresses.

## 7) Preserve Behavior While Refactoring
- Refactoring for readability must not silently change behavior unless explicitly requested.
- When behavior changes are intended, make them explicit and update/add tests accordingly.

## 8) Keep Changes Easy to Review
- Make small, coherent changes grouped by purpose.
- Avoid mixing unrelated refactors with functional changes in the same edit.
