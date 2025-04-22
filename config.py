"""
config.py
---------
Carrega e valida variáveis de ambiente usando
python‑dotenv + pydantic‑settings.
"""

from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# 1) Em desenvolvimento, carrega o arquivo .env
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

# 2) Modelo de configurações
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # —— variáveis obrigatórias ——
    NOTION_TOKEN:        str
    NOTION_DATABASE_ID:  str
    ZAPI_INSTANCE_ID:    str
    ZAPI_TOKEN:          str
    ZAPI_SECURITY_TOKEN: str
    SMTP_USER:           str
    SMTP_PASSWORD:       str

    # —— opcionais (com padrão) ——
    SMTP_SERVER:         str = "smtp.gmail.com"
    SMTP_PORT:           int = 587

# 3) Instância global para ser importada em qualquer parte do projeto
settings = Settings()
