from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base
import os
import dotenv

dotenv.load_dotenv()
engine = create_engine(
    f"{os.getenv("DB_TYPE")}://{os.getenv("DB_USERNAME")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_PATH")}/{os.getenv("DB_DATABASE_NAME")}")
session_factory = sessionmaker(autocommit=False,
                               autoflush=True,
                               bind=engine)
Base = declarative_base()
#Base.query = db_session.query_property()


def init_db():
    # import all modules here that might define models so that
    # they will be registered properly on the metadata.  Otherwise
    # you will have to import them first before calling init_db()
    import models
    Base.metadata.create_all(bind=engine)
