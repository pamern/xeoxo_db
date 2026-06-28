from sqlalchemy import create_engine, text
from src.config.settings import DATABASE_URL, DB_SCHEMA


def get_engine():
    """
    Tạo SQLAlchemy engine để pandas hoặc script load data dùng lại.
    """
    return create_engine(DATABASE_URL)


def test_connection():
    """
    Test kết nối database.
    """
    engine = get_engine()

    with engine.connect() as conn:
        result = conn.execute(text("SELECT current_database(), current_user;"))
        row = result.fetchone()

    print("Connected successfully")
    print("Database:", row[0])
    print("User:", row[1])


def execute_sql_file(sql_file_path):
    """
    Chạy một file SQL, ví dụ tạo bảng.
    """
    engine = get_engine()

    with open(sql_file_path, "r", encoding="utf-8") as file:
        sql = file.read()

    with engine.begin() as conn:
        conn.execute(text(sql))

    print(f"Executed SQL file: {sql_file_path}")