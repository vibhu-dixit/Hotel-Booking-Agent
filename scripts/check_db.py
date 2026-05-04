"""One-off: verify Postgres from DATABASE_URL in .env."""
from __future__ import annotations

from sqlalchemy import create_engine, text

from app.core.config import settings


def main() -> None:
    url = settings.database_url
    tail = url.split("@", 1)[-1] if "@" in url else url
    print("Target (no secrets): ...@" + tail)

    try:
        eng = create_engine(settings.database_url, pool_pre_ping=True)
        with eng.connect() as conn:
            db = conn.execute(text("SELECT current_database()")).scalar_one()
            ver = conn.execute(text("SELECT version()")).scalar_one()
            print("Status: CONNECTED")
            print("Database:", db)
            print("PostgreSQL:", ver.split(",")[0])
            rows = conn.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
                )
            ).fetchall()
            names = [r[0] for r in rows]
            print(f"Tables in public schema: {len(names)}")
            for n in names[:30]:
                print("  -", n)
            if len(names) > 30:
                print("  ...")
    except Exception as e:
        print("Status: FAILED —", type(e).__name__)
        print(str(e)[:800])


if __name__ == "__main__":
    main()
