SET @db := DATABASE();

SET @stmt := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'rag_indexes' AND COLUMN_NAME = 'name'
    ),
    'SELECT 1',
    'ALTER TABLE rag_indexes ADD COLUMN name VARCHAR(256) NULL'
  )
);
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'rag_indexes' AND COLUMN_NAME = 'chunking_strategy'
    ),
    'SELECT 1',
    'ALTER TABLE rag_indexes ADD COLUMN chunking_strategy JSON NULL'
  )
);
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'rag_indexes' AND COLUMN_NAME = 'expires_after'
    ),
    'SELECT 1',
    'ALTER TABLE rag_indexes ADD COLUMN expires_after JSON NULL'
  )
);
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'rag_indexes' AND COLUMN_NAME = 'file_ids'
    ),
    'SELECT 1',
    'ALTER TABLE rag_indexes ADD COLUMN file_ids JSON NULL'
  )
);
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'rag_indexes' AND COLUMN_NAME = 'metadata'
    ),
    'SELECT 1',
    'ALTER TABLE rag_indexes ADD COLUMN metadata JSON NULL'
  )
);
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'rag_indexes' AND COLUMN_NAME = 'index_type'
    ),
    'ALTER TABLE rag_indexes DROP COLUMN index_type',
    'SELECT 1'
  )
);
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'rag_indexes' AND COLUMN_NAME = 'max_chunk_size'
    ),
    'ALTER TABLE rag_indexes DROP COLUMN max_chunk_size',
    'SELECT 1'
  )
);
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'rag_indexes' AND COLUMN_NAME = 'chunk_overlap'
    ),
    'ALTER TABLE rag_indexes DROP COLUMN chunk_overlap',
    'SELECT 1'
  )
);
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;

SET @stmt := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'rag_indexes' AND COLUMN_NAME = 'provider_ttl_days'
    ),
    'ALTER TABLE rag_indexes DROP COLUMN provider_ttl_days',
    'SELECT 1'
  )
);
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
