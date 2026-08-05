"""BOTMARKET — an autonomous agent economy simulation.

Package layout:

* :mod:`botmarket.domain`       - pure simulation logic, no database or HTTP.
* :mod:`botmarket.db`           - SQLAlchemy engine, session and ORM models.
* :mod:`botmarket.repositories` - narrow persistence helpers per aggregate.
* :mod:`botmarket.services`     - use cases that orchestrate domain + storage.
* :mod:`botmarket.api`          - FastAPI routers and wire schemas.

Dependencies point strictly inward: ``api -> services -> repositories -> db``
and every layer may use ``domain``, but ``domain`` imports none of them.
"""

__version__ = "1.0.0"
