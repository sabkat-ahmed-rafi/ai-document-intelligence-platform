from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None
    role: str = "user"


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    role: str = "user"
    is_active: bool = True
    is_verified: bool = True

    model_config = {"from_attributes": True}
