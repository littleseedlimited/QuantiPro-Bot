from src.database.db_manager import DatabaseManager
from src.database.models import User
import sys
import os

# Ensure data dir exists
os.makedirs("data", exist_ok=True)

def promote_admin(user_id):
    db = DatabaseManager()
    session = db.get_session()
    try:
        user = session.query(User).filter(User.telegram_id == user_id).first()
        if user:
            user.is_admin = True
            session.commit()
            print(f"✅ User {user_id} promoted to Admin.")
        else:
            print(f"❌ User {user_id} not found in DB.")
            # Create if not exists (optional, but good for testing)
            # user = User(telegram_id=user_id, is_admin=True, full_name="Admin")
            # session.add(user)
            # session.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    promote_admin(1241907317)
