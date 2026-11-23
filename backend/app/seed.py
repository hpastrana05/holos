from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.models import Household, Role, User

def seed():
    db = SessionLocal()
    try:
        household = db.query(Household).filter_by(name=settings.household_name).first()
        if not household:
            household = Household(name=settings.household_name); db.add(household); db.flush()
        if not db.query(User).filter_by(email=settings.admin_email).first():
            db.add(User(email=settings.admin_email, password_hash=hash_password(settings.admin_password), role=Role.admin, household_id=household.id))
        db.commit()
    finally: db.close()
if __name__ == "__main__": seed()
