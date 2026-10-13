import uuid


class FileNamer:

    def generate(
        self,
        extension
    ):

        return (
            f"{uuid.uuid4()}.{extension}"
        )