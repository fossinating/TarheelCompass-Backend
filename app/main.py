from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.database import init_db
from app.schema import schema
from strawberry.fastapi import GraphQLRouter

app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://tarheelcompass.com",
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
    return [
        {"id": "FALL2023", "name": "Fall 2023", "default": False},
        {"id": "SPRI2024", "name": "Spring 2023", "default": True},
        ]


if __name__ == '__main__':
    init_db()
