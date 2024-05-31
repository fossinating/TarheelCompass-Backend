from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base

import app.config as config

engine = create_engine(
    f"{config.DB_TYPE}://{config.DB_USERNAME}:{config.DB_PASSWORD}@{config.DB_PATH}/{config.DB_DATABASE_NAME}")
session_factory = sessionmaker(autocommit=False,
                               autoflush=True,
                               bind=engine)
Base = declarative_base()
#Base.query = db_session.query_property()


def init_db():
    # import all modules here that might define models so that
    # they will be registered properly on the metadata.  Otherwise
    # you will have to import them first before calling init_db()
    import app.models
    Base.metadata.create_all(bind=engine)