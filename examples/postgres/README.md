# PostgreSQL Adapter Template

This example shows how to back `ProxyManager` with PostgreSQL using SQLAlchemy
Core. It lives outside the packaged library so teams can copy the adapter into
their own services and extend it with organisation-specific migrations.

```
examples/postgres/
├── adapter.py          # Reference `PostgresStorage` implementation
├── tables.py           # SQLAlchemy metadata used by the adapter
├── migrations/
│   └── 0001_init.sql   # Schema bootstrap script
├── docker-compose.yml  # Disposable PostgreSQL for local testing
└── requirements.txt    # Optional dependencies (SQLAlchemy, psycopg, Alembic)
```

## Quickstart

1. **Create a virtual environment** (from the repo root):

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   pip install -r examples/postgres/requirements.txt
   ```

2. **Start PostgreSQL locally**:

   ```bash
   docker compose -f examples/postgres/docker-compose.yml up -d
   ```

3. **Apply the baseline migration** (uses the default `pharox` database/user):

   ```bash
   psql postgresql://pharox:pharox@localhost:5439/pharox \
       -f examples/postgres/migrations/0001_init.sql
   ```

4. **Use the adapter in code**:

   ```python
   from sqlalchemy import create_engine

   from pharox.manager import ProxyManager
   from pharox.models import ProxyPool
   from pharox.storage.in_memory import InMemoryStorage  # for seeding helpers
   from examples.postgres.adapter import PostgresStorage

   engine = create_engine("postgresql+psycopg://pharox:pharox@localhost:5439/pharox")
   storage = PostgresStorage(engine=engine)
   manager = ProxyManager(storage)
   ```

   Migrations manage pools/proxies/consumers. During early testing you can still
   reuse the `bootstrap_*` helpers from `pharox.utils.bootstrap` against the
   in-memory adapter, then copy the data into SQL.

## Migration Notes

- `migrations/0001_init.sql` creates pools, proxies, consumers, and leases with
  the columns required by `PostgresStorage`. Extend this script (or create
  additional numbered files) as your project adds metadata such as tags or pool
  preferences.
- Use your preferred migration tool (Alembic, Flyway, Liquibase). The SQL file
  is intentionally plain so it can be ported easily.
- When adding columns that should hydrate the Pydantic models, update both
  `tables.py` and `adapter.py` so the adapter round-trips the new fields.

## Testing & Hardening

- Point `storage_contract_suite` (coming soon) at `PostgresStorage` to ensure
  it matches the behaviour of the in-memory adapter.
- Add database-level constraints that mirror toolkit invariants (e.g., unique
  pool names, non-negative `current_leases`).
- Replace the naive geo filter in `_distance_km` with PostGIS or `earthdistance`
  when you need production-grade proximity queries.

## Next Steps

- Add indexes that match your filter volume (`country`, `source`, geospatial).
- Layer selector strategies (round-robin / least-used) once the core API lands.
- Document how your service seeds pools and consumers so other teams can reuse
  this template confidently.
