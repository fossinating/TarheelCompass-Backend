from os import getenv


# Database information
DB_TYPE = "postgresql"
DB_USERNAME = "postgres"
with open('/run/secrets/postgres_passwd') as f:
    DB_PASSWORD = f.read().strip()
DB_PATH = getenv("DB_PATH", "localhost")
DB_DATABASE_NAME = getenv("DB_DATABASE_NAME", "coursilium")
