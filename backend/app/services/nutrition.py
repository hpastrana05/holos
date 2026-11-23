from datetime import date

from sqlalchemy.orm import Session

from app.models.models import HealthProfile, NutritionGoal, User, WeightEntry, WeightGoal
from app.services.health import target_kcal


def kcal_target(user: User, db: Session) -> int | None:
    profile = db.query(HealthProfile).filter_by(user_id=user.id).first()
    latest = db.query(WeightEntry).filter_by(user_id=user.id).order_by(WeightEntry.date.desc(), WeightEntry.id.desc()).first()
    goal = db.query(WeightGoal).filter_by(user_id=user.id, active=True).first()
    if not profile or not latest: return None
    return target_kcal(profile.height_cm, profile.birth_date, profile.sex, profile.activity_level, latest.weight_kg, goal.target_weight_kg if goal else None)


def macro_targets(user: User, db: Session, kcal: int | None) -> dict[str, float]:
    goal = db.query(NutritionGoal).filter_by(user_id=user.id).first()
    if goal: return {"protein_g": goal.protein_g, "carbs_g": goal.carbs_g, "fat_g": goal.fat_g}
    calories = kcal or 2000
    return {"protein_g": round(calories * .25 / 4), "carbs_g": round(calories * .45 / 4), "fat_g": round(calories * .30 / 9)}
