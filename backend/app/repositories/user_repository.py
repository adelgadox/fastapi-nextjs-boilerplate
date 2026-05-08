from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):

    def find_by_id(self, user_id: UUID) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def find_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def find_by_username(self, username: str) -> User | None:
        return self.db.query(User).filter(User.username == username).first()

    def find_by_verification_token(self, token: str) -> User | None:
        return self.db.query(User).filter(User.verification_token == token).first()

    def find_by_reset_token(self, token: str) -> User | None:
        return self.db.query(User).filter(User.reset_password_token == token).first()

    def find_active_by_identifier(self, identifier: str) -> User | None:
        """Find active user by email OR username."""
        return self.db.query(User).filter(
            (User.email == identifier) | (User.username == identifier)
        ).first()

    def email_exists(self, email: str) -> bool:
        return self.db.query(User).filter(User.email == email).first() is not None

    def username_exists(self, username: str) -> bool:
        return self.db.query(User).filter(User.username == username).first() is not None

    def save(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def commit(self) -> None:
        self.db.commit()
