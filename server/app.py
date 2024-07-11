import os
from typing import Annotated
from fastapi import Depends, FastAPI
import datetime

from common.database import init_db, session_factory
from common.models import TermData, TermDataSource
from schema import schema
from strawberry.fastapi import GraphQLRouter
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

dev_mode = "dev" in os.environ

app = FastAPI(openapi_url="/openapi.json" if dev_mode else None, docs_url="/docs" if dev_mode else None, redoc_url=None)
app.debug = dev_mode

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:80",
] if app.debug else [
    "https://tarheelcompass.com"
]

graphql_app = GraphQLRouter(schema, graphiql=False)

app.include_router(graphql_app, prefix="/graphql")

db_session = session_factory()


@app.get("/terms")
async def terms():
    stmt = select(TermData).where(TermData.sources.any(TermDataSource.last_seen < (datetime.datetime.now() + datetime.timedelta(days=7))))
    result = db_session.execute(stmt)

    return [{"name": term.name, "id": term.id} for term in result.scalars()]

if __name__ == '__main__':
    init_db()
