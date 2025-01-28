import os
import sys
from dotenv import load_dotenv

load_dotenv()


def getenv(key):
    value = os.getenv(key)
    if value is None:
        sys.exit(f"Переменная окружения {key} не найдена в env")
    return value
