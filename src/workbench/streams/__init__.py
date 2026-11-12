"""Stream builders: one module per stream (platform, usage), each exposing build(ctx).

A builder writes expected and actual billing amounts into `billing_lines` and expected October
revenue into `revenue_lines` for every customer. Only streams with a builder are reconciled.
"""
