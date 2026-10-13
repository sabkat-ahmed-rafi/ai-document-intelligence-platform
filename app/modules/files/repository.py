from sqlalchemy.ext.asyncio import AsyncSession

from .models import File


class FileRepository:

    def __init__(self, session: AsyncSession):
        self.session = session


    async def create(self, file: File):

        self.session.add(file)

        await self.session.commit()

        await self.session.refresh(file)

        return file


    async def get_by_id(self, file_id: str):

        result = await self.session.get(
            File,
            file_id
        )

        return result


    async def delete(self, file: File):

        await self.session.delete(file)

        await self.session.commit()


    async def update(self, file: File):

        await self.session.commit()

        await self.session.refresh(file)

        return file