from pydantic import BaseModel, Field


class NewBook(BaseModel):
    title: str = Field(min_length=1)
    author: str = Field(min_length=1)


class BookOut(BaseModel):
    id: int
    title: str
    author: str
    checked_out_by: str | None


class BookList(BaseModel):
    books: list[BookOut]


class CheckoutRequest(BaseModel):
    member: str = Field(min_length=1)
