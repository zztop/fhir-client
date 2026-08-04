from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # FHIR server
    fhir_base_url: str = "http://localhost:8080/fhir/r4"
    port_fhir: int = 8080

    # Stub payer service ports (used when running via uvicorn directly)
    port_cds: int = 3001
    port_dtr: int = 3002
    port_pas: int = 3003

    # Payer base URLs (EHR side sends requests here)
    payer_cds_base_url: str = "http://localhost:3001"
    payer_dtr_base_url: str = "http://localhost:3002"
    payer_pas_base_url: str = "http://localhost:3003"

    log_level: str = "INFO"
    pend_delay_seconds: int = 0
    enable_auth: bool = False


settings = Settings()
