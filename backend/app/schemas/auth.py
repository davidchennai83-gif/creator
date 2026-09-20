from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(LoginRequest):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=12, max_length=128)
    display_name: str | None = Field(default=None, max_length=255)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=4096)
