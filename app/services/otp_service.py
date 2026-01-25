

import random
from ..extensions import redis_client
from ..config import Config

def generate_and_store_otp(email: str) -> str:
    otp = str(random.randint(100000, 999999))
    redis_client.setex(f"otp:{email}", Config.OTP_EXPIRY, otp)
    redis_client.setex(f"otp_resend_lock:{email}", 30, "1")  # 30 seconds lock
    redis_client.setex(f"otp_attempts:{email}", Config.OTP_EXPIRY, 0)
    return otp

def can_resend_otp(email: str) -> bool:
    return not redis_client.exists(f"otp_resend_lock:{email}")

def verify_otp(email: str, otp: str) -> bool:
    stored_otp = redis_client.get(f"otp:{email}")
    if not stored_otp:
        return False
    stored_otp = stored_otp.decode() if isinstance(stored_otp, bytes) else stored_otp
    if stored_otp == otp:
        redis_client.delete(f"otp:{email}")
        redis_client.delete(f"otp_attempts:{email}")
        return True
    return False

def increment_attempt(email: str) -> bool:
    attempts = redis_client.incr(f"otp_attempts:{email}")
    if attempts > 3:
        redis_client.delete(f"otp:{email}")
        redis_client.delete(f"otp_attempts:{email}")
        return False
    return True
