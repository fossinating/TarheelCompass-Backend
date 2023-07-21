from os import getenv
import my_secrets


# Database information
DB_TYPE = "postgresql"
DB_USERNAME = "postgres"
if getenv("ENVIRONMENT", "dev").lower() == "docker":
    with open('/run/secrets/postgres_passwd') as f:
        DB_PASSWORD = f.read().strip()
else:
    DB_PASSWORD = my_secrets.DB_PASSWORD
DB_PATH = getenv("DB_PATH", "localhost")
DB_DATABASE_NAME = getenv("DB_DATABASE_NAME", "coursilium")


# Config for Flask-WTF Recaptcha necessary for user registration
#RECAPTCHA_PUBLIC_KEY = secrets.RECAPTCHA_PUBLIC_KEY
#RECAPTCHA_PRIVATE_KEY = secrets.RECAPTCHA_PRIVATE_KEY

# Config for Flask-Mail necessary for user registration
MAIL_SERVER = 'smtp.gmail.com'
MAIL_USE_TLS = True
MAIL_PORT = 587
MAIL_USERNAME = 'coursilium@gmail.com'
#MAIL_PASSWORD = secrets.MAIL_PASSWORD
MAIL_DEFAULT_SENDER = ("Coursilium Registration", 'coursilium+registration@gmail.com')
