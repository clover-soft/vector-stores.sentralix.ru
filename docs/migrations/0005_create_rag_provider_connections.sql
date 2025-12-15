CREATE TABLE IF NOT EXISTS rag_provider_connections (
  id VARCHAR(64) NOT NULL,
  base_url VARCHAR(1024) NULL,
  auth_type VARCHAR(32) NOT NULL,

  credentials_enc JSON NULL,
  token_enc JSON NULL,
  token_expires_at DATETIME NULL,

  is_enabled BOOLEAN NOT NULL DEFAULT 1,
  last_healthcheck_at DATETIME NULL,
  last_error TEXT NULL,

  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (id)
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci;
