from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


Role = Literal["listener", "artist", "staff"]
PublicationStatus = Literal["pending", "approved", "rejected"]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    role: Role = "listener"


class UserLogin(BaseModel):
    username: str
    password: str


class UserPublic(BaseModel):
    id: str
    username: str
    email: EmailStr
    role: Role


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class PlaylistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)


class PlaylistAddSong(BaseModel):
    publication_id: str


class Playlist(BaseModel):
    id: str
    owner_id: str
    name: str
    description: str
    song_ids: list[str]
    created_at: datetime


class PublicationMetadata(BaseModel):
    publication_id: str
    artist_id: str
    title: str
    genre: str
    description: str
    song_files: list[str]
    cover_file: str
    status: PublicationStatus = "pending"
    uploaded_at: datetime


class ApprovalAction(BaseModel):
    status: Literal["approved", "rejected"]


class SearchResult(BaseModel):
    publication_id: str
    artist_id: str
    title: str
    genre: str
    status: PublicationStatus
