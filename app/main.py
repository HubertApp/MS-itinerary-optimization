from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from app.schema import schema

graphql_app = GraphQLRouter(schema)

app = FastAPI(title="Mon API GraphQL")

app.include_router(graphql_app, prefix="/graphql")

@app.get("/")
def root():
    return {"message": "API en ligne, va sur /graphql pour le playground"}