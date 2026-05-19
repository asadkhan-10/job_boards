from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from .. import models, database, utils, oauth2
from .. import schemas

router = APIRouter(prefix="/login", tags=["Authentication"])


@router.post("/", response_model=schemas.Token)
def login(
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db),
):
    user = (
        db.query(models.User)
        .filter(models.User.email == user_credentials.username)
        .first()
    )
    if not user:
        raise HTTPException(status_code=403, detail="Invalid Credentials")
    if not utils.verify_password(user_credentials.password, user.password):
        raise HTTPException(status_code=403, detail="Invalid Credentials")
    access_token = oauth2.create_access_token(data={"user_id": user.id})

    return {"access_token": access_token, "token_type": "bearer"}
