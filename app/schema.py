import strawberry
from typing import List



@strawberry.type
class Test:
    title: str

test_db = [
    Test(title="test"),
]

@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "Hello depuis Strawberry GraphQL !"
    
@strawberry.type
class Mutation:
    @strawberry.mutation
    def add_test(self, title: str) -> Test:
        test = Test(title=title)
        test_db.append(test)
        return test

schema = strawberry.Schema(query=Query, mutation=Mutation)