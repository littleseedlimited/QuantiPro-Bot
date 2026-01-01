from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from datetime import datetime
import json

Base = declarative_base()

class Plan(Base):
    __tablename__ = 'plans'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    row_limit = Column(Integer, default=150)
    price_usd = Column(Float, default=0.0)  # Monthly price
    price_yearly = Column(Float, default=0.0)  # Yearly price (25% discount)
    features = Column(String)
    feature_limits = Column(Text)  # JSON with granular feature limits
    
    users = relationship("User", back_populates="plan")
    
    def get_limits(self) -> dict:
        """Get feature limits as dictionary."""
        if self.feature_limits:
            return json.loads(self.feature_limits)
        return {}
    
    def has_feature(self, feature: str) -> bool:
        """Check if plan includes a feature."""
        limits = self.get_limits()
        return limits.get(feature, False) if isinstance(limits.get(feature), bool) else limits.get(feature, 0) > 0
    
    def get_limit(self, feature: str, default=0):
        """Get specific feature limit."""
        return self.get_limits().get(feature, default)
    
    def get_yearly_price(self) -> float:
        """Calculate yearly price with 25% discount."""
        if self.price_yearly and self.price_yearly > 0:
            return self.price_yearly
        # Calculate: monthly * 12 * 0.75 (25% off)
        return round(self.price_usd * 12 * 0.75, 2)
    
    def get_monthly_from_yearly(self) -> float:
        """Get effective monthly price when paying yearly."""
        return round(self.get_yearly_price() / 12, 2)


class User(Base):
    __tablename__ = 'users'
    
    telegram_id = Column(Integer, primary_key=True)
    full_name = Column(String)
    email = Column(String)
    phone = Column(String)
    country = Column(String)
    local_currency = Column(String)
    
    plan_id = Column(Integer, ForeignKey('plans.id'))
    is_admin = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    verification_code = Column(String, nullable=True)
    
    # Institutional Onboarding
    invite_code = Column(String, unique=True, nullable=True)
    institution_admin_id = Column(Integer, ForeignKey('users.telegram_id'), nullable=True)
    
    signup_date = Column(DateTime, default=datetime.utcnow)
    subscription_expiry = Column(DateTime, nullable=True)
    
    plan = relationship("Plan", back_populates="users")
    tasks = relationship("Task", back_populates="user")
    
    # Relationship for institution members
    members = relationship("User", 
                          backref=backref("institution_admin", remote_side=[telegram_id]),
                          uselist=True)


class Task(Base):
    """Stores user analysis sessions for history/continue later functionality."""
    __tablename__ = 'tasks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.telegram_id'))
    
    title = Column(String, default="Untitled Analysis")
    status = Column(String, default="in_progress")  # in_progress, completed, saved
    
    file_path = Column(String)
    research_title = Column(String)
    research_objectives = Column(Text)
    research_questions = Column(Text)
    research_hypothesis = Column(Text)
    
    # Store context data as JSON
    context_data = Column(Text)  # JSON string of user_data
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="tasks")
    
    def set_context(self, data: dict):
        self.context_data = json.dumps(data)
    
    def get_context(self) -> dict:
        return json.loads(self.context_data) if self.context_data else {}
