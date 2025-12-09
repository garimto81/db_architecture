"""
Common Schemas

Shared schemas for pagination, filtering, and enums.
"""
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, List, Optional
from enum import Enum

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints"""
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper"""
    items: List[T]
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")


# Enum definitions matching database constraints

class ProjectCode(str, Enum):
    """Valid project codes"""
    WSOP = "WSOP"
    HCL = "HCL"
    GGMILLIONS = "GGMILLIONS"
    MPP = "MPP"
    PAD = "PAD"
    GOG = "GOG"
    OTHER = "OTHER"


class EventType(str, Enum):
    """Valid event types"""
    BRACELET = "bracelet"
    CIRCUIT = "circuit"
    SUPER_CIRCUIT = "super_circuit"
    HIGH_ROLLER = "high_roller"
    SUPER_HIGH_ROLLER = "super_high_roller"
    CASH_GAME = "cash_game"
    TV_SERIES = "tv_series"
    MYSTERY_BOUNTY = "mystery_bounty"
    MAIN_EVENT = "main_event"


class GameType(str, Enum):
    """Valid game types"""
    NLHE = "NLHE"
    PLO = "PLO"
    PLO8 = "PLO8"
    MIXED = "Mixed"
    STUD = "Stud"
    RAZZ = "Razz"
    HORSE = "HORSE"
    TD27 = "2-7TD"
    SD27 = "2-7SD"
    BADUGI = "Badugi"
    OE = "OE"
    NLO8 = "NLO8"


class SeasonStatus(str, Enum):
    """Valid season status"""
    ACTIVE = "active"
    COMPLETED = "completed"
    UPCOMING = "upcoming"


class EpisodeType(str, Enum):
    """Valid episode types"""
    FULL = "full"
    HIGHLIGHT = "highlight"
    RECAP = "recap"
    INTERVIEW = "interview"
    SUBCLIP = "subclip"


class VersionType(str, Enum):
    """Valid video version types"""
    CLEAN = "clean"
    MASTERED = "mastered"
    STREAM = "stream"
    SUBCLIP = "subclip"
    FINAL_EDIT = "final_edit"
    NOBUG = "nobug"
    PGM = "pgm"
    GENERIC = "generic"
    HIRES = "hires"
