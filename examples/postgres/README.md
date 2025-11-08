# PostgreSQL Adapter Template

This example shows how to back `ProxyManager` with PostgreSQL using SQLAlchemy
Core. The adapter ships inside the `pharox.storage.postgres` package, while this
directory keeps Docker Compose, migrations, and a shim module you can copy into
your own services and extend with organisation-specific changes.

```
examples/postgres/
├── adapter.py          # Legacy shim (re-exports `pharox.storage.postgres`)
├── tables.py           # SQLAlchemy metadata re-exported from the package
├── migrations/
│   └── 0001_init.sql   # Schema bootstrap script
└── docker-compose.yml  # Disposable PostgreSQL for local testing
```

## Quickstart

1. **Create a virtual environment** (from the repo root):

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e '.[postgres]'
   # or via Poetry:
   # poetry install --extras postgres
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
   from pharox.storage.postgres import PostgresStorage

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
  `pharox.storage.postgres.tables` and `pharox.storage.postgres.adapter` so the
  adapter round-trips the new fields (or copy the modules locally if you need
  to diverge).

## Testing & Hardening

- Point `storage_contract_suite` at `PostgresStorage` to ensure it matches the
  behaviour of the in-memory adapter.
- Add database-level constraints that mirror toolkit invariants (e.g., unique
  pool names, non-negative `current_leases`).
- Replace the naive geo filter in `_distance_km` with PostGIS or `earthdistance`
  when you need production-grade proximity queries.

### Run the Contract Suite

The Pharox package ships `StorageContractFixtures` and `storage_contract_suite`
under `pharox.tests.adapters`. Provide adapter-specific seeding helpers and run
the suite via `pytest`:

```python
fixtures = StorageContractFixtures(
    make_storage=make_postgres_storage,
    seed_pool=seed_pool_row,
    seed_proxy=seed_proxy_row,
)
storage_contract_suite(fixtures)
```

This keeps the SQL template compatible with the behaviour expected by
`ProxyManager` and makes it easy to validate downstream forks.

Inside this repository you can run the ready-made test (skips automatically if
no database URL is provided):

```bash
PHAROX_TEST_POSTGRES_URL=postgresql+psycopg://pharox:pharox@localhost:5439/pharox \
    poetry run pytest tests/test_storage_contract_postgres.py
```

## Next Steps

- Add indexes that match your filter volume (`country`, `source`, geospatial).
- Layer selector strategies (round-robin / least-used) once the core API lands.
- Document how your service seeds pools and consumers so other teams can reuse
  this template confidently.
