from sqlalchemy.ext.asyncio import AsyncSession

from .model import Users


class UserRepository:

    def __init__(self, session: AsyncSession):
        self.session = session


    async def get_by_email(self, email: str) -> Users | None:
        from sqlalchemy import select
        result = await self.session.execute(
            select(Users).where(Users.email == email)
        )
        return result.scalar_one_or_none()


    async def get_by_id(self, user_id: str) -> Users | None:
        return await self.session.get(Users, user_id)


    async def create(self, user: Users) -> Users:
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user


    async def update(self, user: Users) -> Users:
        await self.session.commit()
        await self.session.refresh(user)
        return user
