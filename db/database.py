"""
db/database.py - Conexao com o banco SQLite (historico de chats)
================================================================
Reconstruido a partir do bytecode em __pycache__/database.cpython-312.pyc
apos a migracao Windows -> Linux.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./doninha.db"

# check_same_thread=False: o FastAPI usa varias threads (o generator SSE abre sua propria sessao)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
