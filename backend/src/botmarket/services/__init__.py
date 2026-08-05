"""Use cases that orchestrate the domain and the repositories.

Services own the transaction boundary: each public function either commits the
whole use case or raises a :class:`~botmarket.domain.errors.DomainError` and
leaves the session untouched. They know nothing about HTTP.
"""
