from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MetadataResponse
from app.services.analytics_service import get_metadata

router = APIRouter()


@router.get("/metadata", response_model=MetadataResponse)
def metadata(db: Session = Depends(get_db)) -> MetadataResponse:
    return get_metadata(db)
