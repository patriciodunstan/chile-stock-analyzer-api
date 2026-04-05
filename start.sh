#!/bin/bash
set -e

PORT=${PORT:-8000}

# Initialize DB tables
python -c "
import asyncio
from app.infrastructure.persistence.database import init_db
asyncio.run(init_db())
print('Database tables initialized')
"

# Seed data if empty (first deploy)
python -c "
import asyncio
from app.infrastructure.persistence.database import async_session_factory
from app.infrastructure.persistence.repositories.sqlalchemy_financial_repository import SQLAlchemyFinancialRepository

async def check_and_seed():
    async with async_session_factory() as session:
        repo = SQLAlchemyFinancialRepository(session)
        stmt = await repo.get_latest_statement('SQM-B')
        if stmt is None:
            print('Empty DB detected, running seed...')
            from scripts.seed_ipsa_data import seed
            await seed()
        else:
            print(f'DB has data (latest: {stmt.ticker} {stmt.period}), skipping seed')

asyncio.run(check_and_seed())
"

# Start server
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --log-level info --no-access-log
