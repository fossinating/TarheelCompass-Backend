from fastapi import FastAPI

from common.database import init_db
from schema import schema
from strawberry.fastapi import GraphQLRouter

app = FastAPI()
app.debug = True

graphql_app = GraphQLRouter(schema, graphiql=False)

app.include_router(graphql_app, prefix="/graphql")


@app.get("/terms")
async def terms():
    return ["FALL2023"]


if __name__ == '__main__':
    init_db()
