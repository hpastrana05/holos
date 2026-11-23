from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.models import Category, Household, Role, TransactionType, User

DEFAULT_CATEGORIES = {
    "Supermercado": TransactionType.expense, "Nómina": TransactionType.income,
    "Transporte": TransactionType.expense, "Ocio": TransactionType.expense,
    "Salud": TransactionType.expense, "Hogar": TransactionType.expense, "Otros": TransactionType.expense,
}

def seed():
    db = SessionLocal()
    try:
        household = db.query(Household).filter_by(name=settings.household_name).first()
        if not household:
            household = Household(name=settings.household_name); db.add(household); db.flush()
        if not db.query(User).filter_by(email=settings.admin_email).first():
            db.add(User(email=settings.admin_email, password_hash=hash_password(settings.admin_password), role=Role.admin, household_id=household.id))
        existing = {category.name for category in db.query(Category).filter_by(household_id=household.id)}
        for name, kind in DEFAULT_CATEGORIES.items():
            if name not in existing: db.add(Category(household_id=household.id, name=name, kind=kind))
        db.commit()
    finally: db.close()
if __name__ == "__main__": seed()
