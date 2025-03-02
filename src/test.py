from app.core.database_manager import DatabaseManager

db = DatabaseManager()
print(db.get_user_data("test"))