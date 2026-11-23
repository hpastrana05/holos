from collections import defaultdict
from datetime import date
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session
from app.core.security import create_token, current_user, verify_password
from app.db.session import get_db
from app.models.models import Category, HealthProfile, Transaction, User, WeightEntry, WeightGoal
from app.schemas import (CategoryIn, CategoryOut, HealthProfileIn, HealthProfileOut, LoginIn, Token,
                         TransactionIn, TransactionOut, WeightEntryIn, WeightEntryOut, WeightGoalIn, WeightGoalOut)
from app.services.health import estimate_arrival, target_kcal

app = FastAPI(title="Holos API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8080"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def owned(model, item_id, user, db):
    item = db.query(model).filter(model.id == item_id, model.user_id == user.id).first()
    if not item: raise HTTPException(404, "No encontrado")
    return item
def visible_transactions(user):
    return or_(Transaction.user_id == user.id, and_(Transaction.household_id == user.household_id, Transaction.visibility == "shared"))

@app.get("/health")
def health(): return {"status": "ok"}
@app.post("/auth/login", response_model=Token)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash): raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales incorrectas")
    return Token(access_token=create_token(user))

@app.get("/health/profile", response_model=HealthProfileOut | None)
def get_profile(user: User = Depends(current_user), db: Session = Depends(get_db)): return db.query(HealthProfile).filter_by(user_id=user.id).first()
@app.put("/health/profile", response_model=HealthProfileOut)
def put_profile(data: HealthProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.query(HealthProfile).filter_by(user_id=user.id).first()
    if profile:
        for k, v in data.model_dump().items(): setattr(profile, k, v)
    else: profile = HealthProfile(user_id=user.id, **data.model_dump()); db.add(profile)
    db.commit(); db.refresh(profile); return profile

@app.get("/health/weights", response_model=list[WeightEntryOut])
def list_weights(user: User = Depends(current_user), db: Session = Depends(get_db)): return db.query(WeightEntry).filter_by(user_id=user.id).order_by(WeightEntry.date).all()
@app.post("/health/weights", response_model=WeightEntryOut, status_code=201)
def add_weight(data: WeightEntryIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = WeightEntry(user_id=user.id, **data.model_dump()); db.add(item); db.commit(); db.refresh(item); return item
@app.put("/health/weights/{item_id}", response_model=WeightEntryOut)
def edit_weight(item_id: int, data: WeightEntryIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = owned(WeightEntry, item_id, user, db)
    for k,v in data.model_dump().items(): setattr(item,k,v)
    db.commit(); db.refresh(item); return item
@app.delete("/health/weights/{item_id}", status_code=204)
def delete_weight(item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)): db.delete(owned(WeightEntry,item_id,user,db)); db.commit()

@app.get("/health/goals", response_model=list[WeightGoalOut])
def list_goals(user: User = Depends(current_user), db: Session = Depends(get_db)): return db.query(WeightGoal).filter_by(user_id=user.id).order_by(WeightGoal.start_date.desc()).all()
@app.post("/health/goals", response_model=WeightGoalOut, status_code=201)
def add_goal(data: WeightGoalIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if data.active: db.query(WeightGoal).filter_by(user_id=user.id, active=True).update({"active": False})
    item=WeightGoal(user_id=user.id, **data.model_dump()); db.add(item); db.commit(); db.refresh(item); return item
@app.put("/health/goals/{item_id}", response_model=WeightGoalOut)
def edit_goal(item_id:int,data:WeightGoalIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    item=owned(WeightGoal,item_id,user,db)
    if data.active: db.query(WeightGoal).filter(WeightGoal.user_id==user.id, WeightGoal.id!=item.id).update({"active":False})
    for k,v in data.model_dump().items(): setattr(item,k,v)
    db.commit(); db.refresh(item); return item
@app.delete("/health/goals/{item_id}", status_code=204)
def delete_goal(item_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)): db.delete(owned(WeightGoal,item_id,user,db)); db.commit()

@app.get("/health/summary")
def health_summary(user:User=Depends(current_user),db:Session=Depends(get_db)):
    entries=db.query(WeightEntry).filter_by(user_id=user.id).order_by(WeightEntry.date).all(); profile=db.query(HealthProfile).filter_by(user_id=user.id).first(); goal=db.query(WeightGoal).filter_by(user_id=user.id,active=True).first()
    current=entries[-1].weight_kg if entries else None
    kcal=target_kcal(profile.height_cm,profile.birth_date,profile.sex,profile.activity_level,current,goal.target_weight_kg if goal else None) if profile and current else None
    return {"current_weight_kg":current,"trend_kg":(current-entries[0].weight_kg if len(entries)>1 else None),"estimated_goal_date":estimate_arrival(current,goal.target_weight_kg,goal.weekly_rate_kg).isoformat() if current and goal else None,"target_kcal":kcal}

@app.get("/finance/categories", response_model=list[CategoryOut])
def list_categories(user:User=Depends(current_user),db:Session=Depends(get_db)): return db.query(Category).filter_by(household_id=user.household_id).order_by(Category.name).all()
@app.post("/finance/categories", response_model=CategoryOut, status_code=201)
def add_category(data:CategoryIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    item=Category(household_id=user.household_id,**data.model_dump());db.add(item);db.commit();db.refresh(item);return item
@app.put("/finance/categories/{item_id}",response_model=CategoryOut)
def edit_category(item_id:int,data:CategoryIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    item=db.query(Category).filter_by(id=item_id,household_id=user.household_id).first()
    if not item: raise HTTPException(404,"No encontrado")
    for k,v in data.model_dump().items():setattr(item,k,v)
    db.commit();db.refresh(item);return item
@app.delete("/finance/categories/{item_id}",status_code=204)
def delete_category(item_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    item=db.query(Category).filter_by(id=item_id,household_id=user.household_id).first()
    if not item: raise HTTPException(404,"No encontrado")
    db.delete(item);db.commit()

@app.get("/finance/transactions",response_model=list[TransactionOut])
def list_transactions(start:date|None=None,end:date|None=None,user:User=Depends(current_user),db:Session=Depends(get_db)):
    q=db.query(Transaction).filter(visible_transactions(user));
    if start:q=q.filter(Transaction.date>=start)
    if end:q=q.filter(Transaction.date<=end)
    return q.order_by(Transaction.date.desc()).all()
@app.post("/finance/transactions",response_model=TransactionOut,status_code=201)
def add_transaction(data:TransactionIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if data.category_id and not db.query(Category).filter_by(id=data.category_id,household_id=user.household_id).first():raise HTTPException(422,"Categoría inválida")
    item=Transaction(user_id=user.id,household_id=user.household_id,**data.model_dump());db.add(item);db.commit();db.refresh(item);return item
@app.put("/finance/transactions/{item_id}",response_model=TransactionOut)
def edit_transaction(item_id:int,data:TransactionIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    item=owned(Transaction,item_id,user,db)
    for k,v in data.model_dump().items():setattr(item,k,v)
    db.commit();db.refresh(item);return item
@app.delete("/finance/transactions/{item_id}",status_code=204)
def delete_transaction(item_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):db.delete(owned(Transaction,item_id,user,db));db.commit()

@app.get("/finance/summary/monthly")
def monthly_summary(year:int=Query(...),month:int=Query(...,ge=1,le=12),user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.query(Transaction.kind,func.sum(Transaction.amount)).filter(visible_transactions(user),func.strftime("%Y",Transaction.date)==str(year),func.strftime("%m",Transaction.date)==f"{month:02d}").group_by(Transaction.kind).all()
    totals={str(k.value):float(v) for k,v in rows};income=totals.get("income",0);expense=totals.get("expense",0);return {"income":income,"expense":expense,"balance":income-expense}
@app.get("/finance/summary/categories")
def category_summary(start:date,end:date,user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.query(Category.name,Transaction.kind,func.sum(Transaction.amount)).outerjoin(Category,Transaction.category_id==Category.id).filter(visible_transactions(user),Transaction.date.between(start,end)).group_by(Category.name,Transaction.kind).all()
    return [{"category":name or "Sin categoría","kind":kind.value,"amount":float(amount)} for name,kind,amount in rows]
