from enum import Enum


class FileCategory(str, Enum):
    DOCUMENT = "document"


class OwnerType(str, Enum):
    USER = "user"
    DOCUMENT = "document"


class FileStatus(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"
    PENDING = "pending"