from datetime import date, datetime, time, timedelta
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agent_routes import provider
from app.core.security import current_user
from app.db.session import get_db
from app.models.models import Meal, MealSource, NutritionGoal, User
from app.schemas import MealEstimate, MealIn, MealOut, NutritionAnalysisOut, NutritionGoalIn, NutritionGoalOut
from app.services.llm import LLMProvider, LLMQuotaExceeded, LLMUnavailable
from app.services.nutrition import kcal_target, macro_targets

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


def goal_out(goal: NutritionGoal | None, user: User, db: Session):
    kcal = kcal_target(user, db)
    macros = macro_targets(user, db, kcal)
    return {"id": goal.id if goal else 0, "user_id": user.id, "kcal": kcal, **macros}


def owned(meal_id: int, user: User, db: Session) -> Meal:
    meal = db.query(Meal).filter_by(id=meal_id, user_id=user.id).first()
    if not meal: raise HTTPException(404, "Comida no encontrada")
    return meal


def resize_photo(raw: bytes, content_type: str | None) -> tuple[bytes, str]:
    if len(raw) > 10 * 1024 * 1024: raise HTTPException(413, "La foto supera el límite de 10 MB")
    if content_type not in {"image/jpeg", "image/png", "image/webp"}: raise HTTPException(415, "Usa una imagen JPEG, PNG o WebP")
    try:
        image = Image.open(BytesIO(raw)); image.thumbnail((1024, 1024))
        if image.mode not in ("RGB", "L"): image = image.convert("RGB")
        output = BytesIO(); image.save(output, format="JPEG", quality=85, optimize=True)
        return output.getvalue(), "image/jpeg"
    except (UnidentifiedImageError, OSError) as error:
        raise HTTPException(422, "No se ha podido leer la foto") from error


@router.get("/goals", response_model=NutritionGoalOut)
def get_goals(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return goal_out(db.query(NutritionGoal).filter_by(user_id=user.id).first(), user, db)


@router.put("/goals", response_model=NutritionGoalOut)
def put_goals(data: NutritionGoalIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    goal = db.query(NutritionGoal).filter_by(user_id=user.id).first()
    if goal:
        for key, value in data.model_dump().items(): setattr(goal, key, value)
    else:
        goal = NutritionGoal(user_id=user.id, **data.model_dump()); db.add(goal)
    db.commit(); db.refresh(goal)
    return goal_out(goal, user, db)


@router.post("/analyze", response_model=NutritionAnalysisOut)
async def analyze(text: str | None = Form(None, max_length=2000), photo: UploadFile | None = File(None), user: User = Depends(current_user), llm: LLMProvider = Depends(provider)):
    if not text and not photo: raise HTTPException(422, "Escribe una descripción o añade una foto")
    image = mime = None
    if photo:
        image, mime = resize_photo(await photo.read(), photo.content_type)
    try:
        items = llm.analyze_meal(text=text, image=image, mime_type=mime)
    except LLMQuotaExceeded as error: raise HTTPException(429, str(error)) from error
    except LLMUnavailable as error: raise HTTPException(503, str(error)) from error
    source = MealSource.photo if image else MealSource.text
    estimates = []
    for item in items:
        try:
            estimates.append(MealEstimate(eaten_at=datetime.now(), meal_type="snack", source=source, **item))
        except (TypeError, ValueError): continue
    return {"meals": estimates}


@router.get("/meals", response_model=list[MealOut])
def list_meals(day: date = date.today(), user: User = Depends(current_user), db: Session = Depends(get_db)):
    start = datetime.combine(day, time.min); end = start + timedelta(days=1)
    return db.query(Meal).filter(Meal.user_id == user.id, Meal.eaten_at >= start, Meal.eaten_at < end).order_by(Meal.eaten_at).all()


@router.post("/meals", response_model=MealOut, status_code=201)
def create_meal(data: MealIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    meal = Meal(user_id=user.id, **data.model_dump()); db.add(meal); db.commit(); db.refresh(meal); return meal


@router.put("/meals/{meal_id}", response_model=MealOut)
def update_meal(meal_id: int, data: MealIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    meal = owned(meal_id, user, db)
    for key, value in data.model_dump().items(): setattr(meal, key, value)
    db.commit(); db.refresh(meal); return meal


@router.delete("/meals/{meal_id}", status_code=204)
def delete_meal(meal_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(owned(meal_id, user, db)); db.commit()


@router.get("/summary")
def summary(day: date = date.today(), user: User = Depends(current_user), db: Session = Depends(get_db)):
    start = datetime.combine(day, time.min); end = start + timedelta(days=1)
    meals = db.query(Meal).filter(Meal.user_id == user.id, Meal.eaten_at >= start, Meal.eaten_at < end).order_by(Meal.eaten_at).all()
    totals = {key: round(sum(getattr(meal, key) for meal in meals), 1) for key in ("kcal", "protein_g", "carbs_g", "fat_g")}
    kcal = kcal_target(user, db); macros = macro_targets(user, db, kcal)
    series = []
    for offset in range(6, -1, -1):
        cursor = day - timedelta(days=offset); a = datetime.combine(cursor, time.min); b = a + timedelta(days=1)
        value = db.query(func.coalesce(func.sum(Meal.kcal), 0)).filter(Meal.user_id == user.id, Meal.eaten_at >= a, Meal.eaten_at < b).scalar()
        series.append({"date": cursor.isoformat(), "kcal": float(value)})
    return {"day": day.isoformat(), "meals": meals, "totals": totals, "target_kcal": kcal, "macro_targets": macros, "series": series}
