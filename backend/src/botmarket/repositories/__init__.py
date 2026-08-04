"""Persistence helpers, one module per aggregate.

Repositories own the queries. They ``flush`` so callers can read generated
primary keys, but never ``commit`` — transaction boundaries belong to the
service layer, so a single use case can span several repositories atomically.
"""
