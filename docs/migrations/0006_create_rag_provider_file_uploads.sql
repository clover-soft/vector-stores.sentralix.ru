CREATE TABLE IF NOT EXISTS rag_provider_file_uploads (
  id VARCHAR(36) NOT NULL,

  provider_id VARCHAR(64) NOT NULL,
  local_file_id VARCHAR(36) NOT NULL,

  external_file_id VARCHAR(255) NULL,
  external_uploaded_at DATETIME NULL,

  content_sha256 CHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  last_error TEXT NULL,
  raw_provider_json JSON NULL,

  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  UNIQUE KEY uq_rag_provider_file_uploads_provider_file (provider_id, local_file_id),
  INDEX ix_rag_provider_file_uploads_provider_id (provider_id),
  INDEX ix_rag_provider_file_uploads_local_file_id (local_file_id)
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci;
