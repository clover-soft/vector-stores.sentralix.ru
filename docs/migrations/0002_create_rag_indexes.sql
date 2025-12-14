CREATE TABLE IF NOT EXISTS rag_indexes (
  id VARCHAR(36) NOT NULL,
  domain_id VARCHAR(128) NOT NULL,

  provider_type VARCHAR(32) NOT NULL,
  external_id VARCHAR(256) NULL,

  index_type VARCHAR(16) NOT NULL,
  max_chunk_size INT NULL,
  chunk_overlap INT NULL,

  indexing_status VARCHAR(32) NOT NULL DEFAULT 'not_indexed',
  indexed_at DATETIME NULL,

  provider_ttl_days INT NULL,
  description TEXT NULL,

  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  INDEX ix_rag_indexes_domain_id (domain_id)
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS rag_index_files (
  index_id VARCHAR(36) NOT NULL,
  file_id VARCHAR(36) NOT NULL,
  include_order INT NOT NULL,

  PRIMARY KEY (index_id, file_id),
  INDEX ix_rag_index_files_index_id (index_id),
  INDEX ix_rag_index_files_file_id (file_id),

  CONSTRAINT fk_rag_index_files_index_id
    FOREIGN KEY (index_id) REFERENCES rag_indexes(id)
    ON DELETE CASCADE,

  CONSTRAINT fk_rag_index_files_file_id
    FOREIGN KEY (file_id) REFERENCES rag_files(id)
    ON DELETE CASCADE
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci;
