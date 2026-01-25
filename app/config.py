
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = "jwt-secret-key-123"   

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URI",
        "mysql://root:Mahek%40123@localhost:3306/login_signup_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    REDIS_HOST = "localhost"
    REDIS_PORT = 6379
    REDIS_DB = 0

    OTP_EXPIRY = 180

    EMAIL_HOST = "smtp.gmail.com"
    EMAIL_PORT = 587
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASS = os.getenv("EMAIL_PASS")
