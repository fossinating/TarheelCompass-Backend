from os import getenv
import secrets

#SECRET_KEY = secrets.SECRET_KEY
#WTF_CSRF_SECRET_KEY = secrets.WTF_CSRF_SECRET_KEY
#SECURITY_CSRF_IGNORE_UNAUTH_ENDPOINTS = True
#WTF_CSRF_CHECK_DEFAULT = False
SESSION_COOKIE_SAMESITE = 'Lax'

SECURITY_PASSWORD_HASH = "argon2"

# user registration information
SECURITY_REGISTERABLE = True
SECURITY_USERNAME_ENABLE = True
SECURITY_USERNAME_REQUIRED = True
SECURITY_PASSWORD_CHECK_BREACHED = True
SECURITY_PASSWORD_BREACHED_COUNT = 50
SECURITY_PASSWORD_COMPLEXITY_CHECKER = "zxcvbn"

AUTH_TYPE = 1  # Database Authentication
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = 'Public'
FAB_PASSWORD_COMPLEXITY_ENABLED = True

# Database information
DB_TYPE = "postgresql"
DB_USERNAME = "postgres"
DB_PASSWORD = secrets.DB_PASSWORD
DB_PATH = "localhost"
DB_DATABASE_NAME = "coursilium"


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
