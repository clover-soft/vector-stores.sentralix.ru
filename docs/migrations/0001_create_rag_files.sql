CREATE TABLE IF NOT EXISTS rag_files (
  id VARCHAR(36) NOT NULL,
  domain_id VARCHAR(128) NOT NULL,

  file_name VARCHAR(512) NOT NULL,
  file_type VARCHAR(128) NOT NULL,
  local_path VARCHAR(1024) NOT NULL,
  size_bytes BIGINT NOT NULL,

  chunking_strategy JSON NULL,

  tags JSON NULL,
  notes TEXT NULL,

  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  INDEX ix_rag_files_domain_id (domain_id)
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci;
