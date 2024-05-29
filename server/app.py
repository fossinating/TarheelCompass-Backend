import os
from fastapi import FastAPI

from common.database import init_db
from schema import schema
from strawberry.fastapi import GraphQLRouter
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.debug = "dev" in os.environ

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:80",
] if app.debug else [
    "https://tarheelcompass.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

graphql_app = GraphQLRouter(schema, graphiql=False)

app.include_router(graphql_app, prefix="/graphql")


@app.get("/terms")
async def terms():
    return ["FALL2023"]


if __name__ == '__main__':
    init_db()
