from pydantic import BaseModel


class PhotoResponse(BaseModel):
    id: int
    filename: str
    original_name: str
    mime_type: str
    file_size: int
    created_at: str
    analysis: str | None = None
    analyzed_at: str | None = None
    image_url: str


class PhotoListResponse(BaseModel):
    photos: list[PhotoResponse]
    total: int


class UploadResponse(BaseModel):
    id: int
    filename: str
    status: str


class AnalysisResponse(BaseModel):
    id: int
    analysis: str
    model: str
    usage: dict


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str


class ErrorResponse(BaseModel):
    detail: str
