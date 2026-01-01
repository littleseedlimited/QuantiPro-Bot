import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload
from src.database.models import Base, User, Plan, Task
from datetime import datetime, timedelta

class DatabaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            db_url = os.getenv("DATABASE_URL", "sqlite:///quantiprobot.db")
            cls._instance.engine = create_engine(db_url)
            Base.metadata.create_all(cls._instance.engine)
            cls._instance.Session = sessionmaker(bind=cls._instance.engine)
            cls._instance.seed_plans()
        return cls._instance

    def get_session(self):
        return self.Session()

    def seed_plans(self):
        import json
        session = self.get_session()
        if session.query(Plan).count() == 0:
            # Feature limits for each plan
            free_limits = json.dumps({
                "analyses_per_session": 5,
                "ai_interpretations_daily": 2,
                "ai_interpretation_length": "short",  # short = 50 words max
                "ai_chat": True,  # AI chat for custom analysis
                "crosstab_max": "2x2",
                "visuals_per_session": 3,
                "saved_projects": 1,
                "references": 0,
                "manuscript_export": False,
                "word_count_custom": False,
                "advanced_stats": False,
                "descriptive_full": False
            })

            
            basic_limits = json.dumps({
                "ai_interpretations_daily": 10,
                "ai_interpretation_length": "medium",  # medium = 100 words
                "crosstab_max": "2x2",
                "visuals_per_session": 10,
                "saved_projects": 5,
                "references": 20,
                "manuscript_export": True,
                "manuscript_structures": ["imrad"],
                "word_count_custom": False,
                "advanced_stats": True,
                "descriptive_full": True
            })
            
            pro_limits = json.dumps({
                "ai_interpretations_daily": 50,
                "ai_interpretation_length": "full",  # full = 150 words
                "crosstab_max": "nxn",
                "visuals_per_session": 999,
                "saved_projects": 20,
                "references": 100,
                "manuscript_export": True,
                "manuscript_structures": ["imrad", "apa", "thesis", "journal", "report"],
                "word_count_custom": True,
                "advanced_stats": True,
                "descriptive_full": True,
                "regression": True,
                "reliability": True
            })
            
            enterprise_limits = json.dumps({
                "ai_interpretations_daily": 9999,
                "ai_interpretation_length": "full",
                "crosstab_max": "nxn",
                "visuals_per_session": 9999,
                "saved_projects": 9999,
                "references": 9999,
                "manuscript_export": True,
                "manuscript_structures": ["imrad", "apa", "thesis", "journal", "report", "custom"],
                "word_count_custom": True,
                "advanced_stats": True,
                "descriptive_full": True,
                "regression": True,
                "reliability": True,
                "priority_support": True,
                "custom_branding": True
            })
            
            limitless_limits = json.dumps({
                "ai_interpretations_daily": 99999,
                "ai_interpretation_length": "full",
                "crosstab_max": "nxn",
                "visuals_per_session": 99999,
                "saved_projects": 99999,
                "references": 99999,
                "manuscript_export": True,
                "manuscript_structures": ["imrad", "apa", "thesis", "journal", "report", "custom"],
                "word_count_custom": True,
                "advanced_stats": True,
                "descriptive_full": True,
                "regression": True,
                "reliability": True,
                "priority_support": True,
                "custom_branding": True,
                "admin_access": True
            })
            
            plans = [
                Plan(name="Free", row_limit=150, price_usd=0.0, 
                     features="5 analyses, 2 AI/day, Basic stats, 150 rows",
                     feature_limits=free_limits),
                Plan(name="Student", row_limit=500, price_usd=9.99, 
                     features="500 rows, 10 AI/day, IMRAD export, 5 projects",
                     feature_limits=basic_limits),
                Plan(name="Researcher", row_limit=5000, price_usd=24.99, 
                     features="5000 rows, 50 AI/day, All exports, Regression",
                     feature_limits=pro_limits),
                Plan(name="Institution", row_limit=1000000, price_usd=149.00, 
                     features="20 seats, Priority support, Team Dashboard, Unlimited",
                     feature_limits=enterprise_limits),
                Plan(name="Limitless", row_limit=999999999, price_usd=0.0, 
                     features="Super Admin - All Features Unlocked Forever",
                     feature_limits=limitless_limits)
            ]
            session.add_all(plans)
            session.commit()
        session.close()



    def update_existing_plans(self):
        """Update existing plans with new pricing and feature limits."""
        import json
        session = self.get_session()
        
        # Mapping old names to new names
        renames = {
            "Basic": "Student",
            "Professional": "Researcher",
            "Enterprise": "Institution"
        }
        
        for old_name, new_name in renames.items():
            plan = session.query(Plan).filter(Plan.name == old_name).first()
            if plan:
                plan.name = new_name
        
        session.commit()

        # Update values
        plan_updates = {
            "Free": {"price_usd": 0.0, "row_limit": 150, "features": "5 analyses, 2 AI/day, Basic stats, 150 rows"},
            "Student": {"price_usd": 9.99, "row_limit": 500, "features": "500 rows, 10 AI/day, IMRAD export, 5 projects"},
            "Researcher": {"price_usd": 24.99, "row_limit": 5000, "features": "5000 rows, 50 AI/day, All exports, Regression"},
            "Institution": {"price_usd": 149.00, "row_limit": 1000000, "features": "20 seats, Priority support, Team Dashboard, Unlimited"},
        }
        
        for plan_name, updates in plan_updates.items():
            plan = session.query(Plan).filter(Plan.name == plan_name).first()
            if plan:
                plan.price_usd = updates["price_usd"]
                plan.row_limit = updates["row_limit"]
                plan.features = updates["features"]
        
        session.commit()
        session.close()

    def update_user_profile(self, telegram_id: int, **kwargs):
        """Update user profile fields."""
        session = self.get_session()
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            session.commit()
        session.close()

    # ==================== INSTITUTIONAL METHODS ====================

    def generate_invite_code(self, admin_id: int) -> str:
        """Generate a unique invite code for an institutional admin."""
        import secrets
        import string
        session = self.get_session()
        user = session.query(User).filter(User.telegram_id == admin_id).first()
        if user and user.plan and user.plan.name == "Institution":
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            user.invite_code = code
            session.commit()
            session.close()
            return code
        session.close()
        return None

    def join_institution(self, user_id: int, invite_code: str) -> dict:
        """Join an institution via invite code."""
        session = self.get_session()
        admin = session.query(User).filter(User.invite_code == invite_code).first()
        if not admin:
            session.close()
            return {"error": "Invalid invite code."}
        
        # Check seat limit (20)
        member_count = session.query(User).filter(User.institution_admin_id == admin.telegram_id).count()
        if member_count >= 20:
            session.close()
            return {"error": "This institution has reached its 20-member limit."}
        
        user = session.query(User).filter(User.telegram_id == user_id).first()
        if user:
            user.institution_admin_id = admin.telegram_id
            user.plan_id = admin.plan_id
            user.subscription_expiry = admin.subscription_expiry
            session.commit()
            session.close()
            return {"success": f"Joined institution lead by {admin.full_name}"}
            
        session.close()
        return {"error": "User not found."}

    def get_institution_members(self, admin_id: int) -> list:
        """Get all members belonging to an institution."""
        session = self.get_session()
        members = session.query(User).filter(User.institution_admin_id == admin_id).all()
        result = [{"id": m.telegram_id, "name": m.full_name, "email": m.email} for m in members]
        session.close()
        return result

    def get_user_feature_limit(self, telegram_id: int, feature: str, default=0):
        """Get a specific feature limit for a user based on their plan."""
        user = self.get_user(telegram_id)
        if user and user.plan:
            return user.plan.get_limit(feature, default)
        return default

    def user_has_feature(self, telegram_id: int, feature: str) -> bool:
        """Check if user's plan includes a feature."""
        user = self.get_user(telegram_id)
        if user and user.plan:
            return user.plan.has_feature(feature)
        return False

    def get_user(self, telegram_id: int):

        session = self.get_session()
        user = session.query(User).options(joinedload(User.plan)).filter(User.telegram_id == telegram_id).first()
        session.close()
        return user

    def create_user(self, telegram_id: int, **kwargs):
        session = self.get_session()
        free_plan = session.query(Plan).filter(Plan.name == "Free").first()
        expiry = datetime.utcnow() + timedelta(days=365)
        user = User(
            telegram_id=telegram_id, 
            plan_id=free_plan.id, 
            subscription_expiry=expiry,
            **kwargs
        )
        session.add(user)
        session.commit()
        user = session.query(User).options(joinedload(User.plan)).filter(User.telegram_id == telegram_id).first()
        session.close()
        return user

    def update_user_profile(self, telegram_id: int, **kwargs):
        session = self.get_session()
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            session.commit()
        session.close()

    def delete_user(self, telegram_id: int):
        session = self.get_session()
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            session.delete(user)
            session.commit()
        session.close()

    def update_user_plan(self, telegram_id: int, plan_name: str):
        session = self.get_session()
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        plan = session.query(Plan).filter(Plan.name == plan_name).first()
        if user and plan:
            user.plan_id = plan.id
            session.commit()
        session.close()

    def get_plans_with_currency(self, currency_code: str):
        session = self.get_session()
        plans = session.query(Plan).all()
        
        rates = {"NGN": 1500, "GHS": 12, "GBP": 0.8, "EUR": 0.9, "USD": 1.0}
        rate = rates.get(currency_code, 1.0)
        
        results = []
        for p in plans:
            results.append({
                "name": p.name,
                "rows": p.row_limit,
                "price_usd": p.price_usd,
                "price_local": p.price_usd * rate,
                "currency": currency_code,
                "features": p.features
            })
        session.close()
        return results

    # ==================== TASK HISTORY METHODS ====================
    
    def save_task(self, user_id: int, title: str, file_path: str, context_data: dict, status: str = "saved"):
        session = self.get_session()
        task = Task(
            user_id=user_id,
            title=title,
            file_path=file_path,
            research_title=context_data.get('research_title', ''),
            research_objectives=context_data.get('research_objectives', ''),
            research_questions=context_data.get('research_questions', ''),
            research_hypothesis=context_data.get('research_hypothesis', ''),
            status=status
        )
        task.set_context(context_data)
        session.add(task)
        session.commit()
        task_id = task.id
        session.close()
        return task_id

    def get_user_tasks(self, user_id: int, limit: int = 10):
        session = self.get_session()
        tasks = session.query(Task).filter(Task.user_id == user_id).order_by(Task.updated_at.desc()).limit(limit).all()
        result = []
        for t in tasks:
            result.append({
                'id': t.id,
                'title': t.title or t.research_title or 'Untitled',
                'status': t.status,
                'created': t.created_at.strftime('%Y-%m-%d %H:%M'),
                'file_path': t.file_path
            })
        session.close()
        return result

    def get_task(self, task_id: int):
        session = self.get_session()
        task = session.query(Task).filter(Task.id == task_id).first()
        if task:
            data = {
                'id': task.id,
                'title': task.title,
                'file_path': task.file_path,
                'context': task.get_context(),
                'status': task.status
            }
            session.close()
            return data
        session.close()
        return None

    def update_task_status(self, task_id: int, status: str):
        session = self.get_session()
        task = session.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = status
            session.commit()
        session.close()

    def delete_task(self, task_id: int, user_id: int) -> bool:
        """Delete a task if it belongs to the user."""
        session = self.get_session()
        task = session.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if task:
            session.delete(task)
            session.commit()
            session.close()
            return True
        session.close()
        return False

    def update_task(self, task_id: int, user_id: int, **kwargs) -> bool:
        """Update task fields (title, context_data, etc.)."""
        session = self.get_session()
        task = session.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if task:
            for key, value in kwargs.items():
                if hasattr(task, key):
                    if key == 'context_data' and isinstance(value, dict):
                        task.set_context(value)
                    else:
                        setattr(task, key, value)
            session.commit()
            session.close()
            return True
        session.close()
        return False

    # ==================== ADMIN METHODS ====================
    
    def get_all_users(self, limit: int = 50):
        session = self.get_session()
        users = session.query(User).options(joinedload(User.plan)).limit(limit).all()
        result = []
        for u in users:
            expiry_str = u.subscription_expiry.strftime('%Y-%m-%d') if u.subscription_expiry else 'N/A'
            result.append({
                'id': u.telegram_id,
                'name': u.full_name or 'Unknown',
                'email': u.email or 'N/A',
                'phone': u.phone or 'N/A',
                'country': u.country or 'N/A',
                'plan': u.plan.name if u.plan else 'Free',
                'expiry': expiry_str,
                'signup_date': u.signup_date.strftime('%Y-%m-%d') if u.signup_date else 'N/A',
                'verified': u.is_verified,
                'admin': u.is_admin
            })
        session.close()
        return result

    def verify_user(self, telegram_id: int):
        session = self.get_session()
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            user.is_verified = True
            session.commit()
        session.close()

    def set_admin(self, telegram_id: int, is_admin: bool):
        session = self.get_session()
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            user.is_admin = is_admin
            session.commit()
        session.close()

    def save_active_session(self, user_id: int, file_path: str, context_data: dict):
        """Save text active session for the user."""
        session = self.get_session()
        # Check if active session exists
        task = session.query(Task).filter(Task.user_id == user_id, Task.status == 'active_session').first()
        if task:
            task.file_path = file_path
            task.set_context(context_data)
            task.updated_at = datetime.utcnow()
        else:
            task = Task(
                user_id=user_id,
                title="Current Session",
                file_path=file_path,
                status='active_session'
            )
            task.set_context(context_data)
            session.add(task)
        session.commit()
        session.close()

    def get_active_session(self, user_id: int):
        """Get the user's current active session."""
        session = self.get_session()
        task = session.query(Task).filter(Task.user_id == user_id, Task.status == 'active_session').first()
        result = None
        if task:
            result = {
                'file_path': task.file_path,
                'context': task.get_context()
            }
        session.close()
        return result

