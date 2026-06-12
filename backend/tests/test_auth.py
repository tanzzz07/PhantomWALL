import sys
import os
import unittest
from datetime import datetime, timezone

# Resolve absolute path to the backend directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set dummy env variables
os.environ["PHANTOMWALL_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["PHANTOMWALL_JWT_SECRET_KEY"] = "dummy-secret-key-12345678901234567890"

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models import Base, User, Install
from app.core.security import hash_password, verify_password
from app.services.auth import create_access_token, decode_admin_access_token
from app.core.config import Settings


class TestAuthAndScoping(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Initialize in-memory DB
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        self.async_session_factory = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        self.settings = Settings(
            admin_username="admin",
            admin_password="password",
            jwt_secret_key="dummy-secret-key-12345678901234567890",
            jwt_algorithm="HS256"
        )

    async def asyncTearDown(self):
        await self.engine.dispose()

    def test_password_hashing(self):
        raw_pw = "my-secure-password"
        hashed = hash_password(raw_pw)
        self.assertNotEqual(raw_pw, hashed)
        self.assertTrue(verify_password(raw_pw, hashed))
        self.assertFalse(verify_password("wrong-pw", hashed))

    async def test_user_registration_and_login(self):
        async with self.async_session_factory() as session:
            # 1. Register a user
            username = "testuser"
            password = "testpassword"
            
            # Check if user exists (should not)
            from sqlalchemy import select
            result = await session.execute(select(User).where(User.username == username))
            self.assertIsNone(result.scalar_one_or_none())
            
            hashed_pw = hash_password(password)
            new_user = User(username=username, password_hash=hashed_pw)
            session.add(new_user)
            await session.commit()
            
            # Retrieve user
            result = await session.execute(select(User).where(User.username == username))
            db_user = result.scalar_one_or_none()
            self.assertIsNotNone(db_user)
            self.assertEqual(db_user.username, username)
            self.assertTrue(verify_password(password, db_user.password_hash))

    async def test_jwt_token_generation_and_decoding(self):
        username = "tokenuser"
        token, expires_at = create_access_token(
            username=username,
            settings=self.settings,
            scope="user",
            user_id="user-uuid-123"
        )
        self.assertIsNotNone(token)
        self.assertGreater(expires_at, datetime.now(timezone.utc))
        
        payload = decode_admin_access_token(token, self.settings)
        self.assertEqual(payload["sub"], username)
        self.assertEqual(payload["scope"], "user")
        self.assertEqual(payload["user_id"], "user-uuid-123")


if __name__ == "__main__":
    unittest.main()
