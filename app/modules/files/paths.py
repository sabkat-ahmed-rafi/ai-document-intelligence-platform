class FilePath:

    def generate(
        self,
        *,
        owner_type: str,
        owner_id: str,
        category: str,
        filename: str,
    ) -> str:
        ot = owner_type.value if hasattr(owner_type, "value") else str(owner_type)
        cat = category.value if hasattr(category, "value") else str(category)
        return f"{ot}/{owner_id}/{cat}/{filename}"