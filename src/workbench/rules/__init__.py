"""Finding rules: one module per root cause, each exposing detect(ctx) -> list[Finding].

Rules read the reconciliations and source tables, and claim the differences they explain.
"""
