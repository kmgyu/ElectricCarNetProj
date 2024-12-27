import os
import sqlite3

# 데이터베이스 경로 설정
current_directory = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_directory, "database.db")

def get_db():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 데이터 사용 가능
    return conn

def drop_tables():
    tables = ["board", "comments", "liked_comment", "liked_question"]  # 삭제할 테이블 목록
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"Table {table} dropped successfully.")
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error dropping tables: {e}")
    finally:
        conn.close()

# 테이블 삭제 함수 호출
drop_tables()
