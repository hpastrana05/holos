from datetime import date, timedelta

ACTIVITY = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725, "very_active": 1.9}
def age_on(birth_date: date, today: date | None = None) -> int:
    today = today or date.today(); return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
def target_kcal(height_cm: float, birth_date: date, sex: str, activity: str, weight_kg: float, goal_weight_kg: float | None) -> int:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age_on(birth_date) + (5 if sex.lower() in ("male", "m", "hombre") else -161)
    maintenance = base * ACTIVITY.get(activity, 1.2)
    if goal_weight_kg is None: return round(maintenance)
    # Maximum deficit/surplus: 500 kcal/day, a conservative ~0.5 kg/week.
    adjustment = -500 if goal_weight_kg < weight_kg else (300 if goal_weight_kg > weight_kg else 0)
    return round(max(1200 if sex.lower() not in ("male", "m", "hombre") else 1500, maintenance + adjustment))
def estimate_arrival(current: float, target: float, weekly_rate: float, today: date | None = None) -> date | None:
    if weekly_rate <= 0: return None
    return (today or date.today()) + timedelta(days=round(abs(target-current) / weekly_rate * 7))
