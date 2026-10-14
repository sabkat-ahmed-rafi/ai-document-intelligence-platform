from pydantic import BaseModel, EmailStr, Field

from modules.users.schemas import UserResponse


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    first_name: str | None = None
    last_name: str | None = None


class LoginResponse(BaseModel):
    user: UserResponse
    token: Token


class RefreshTokenRequest(BaseModel):
    refresh_token: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=72)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyPasswordResetCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


class PasswordResetAuthorization(BaseModel):
    reset_token: str
    expires_in_seconds: int


class ResetPasswordRequest(BaseModel):
    reset_token: str = Field(min_length=32)
    new_password: str = Field(min_length=6, max_length=72)
