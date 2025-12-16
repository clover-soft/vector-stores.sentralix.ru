SET @db := DATABASE();

SET @stmt := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'rag_files' AND COLUMN_NAME = 'external_file_id'
    ),
    'ALTER TABLE rag_files DROP COLUMN external_file_id',
    'SELECT 1'
  )
);

PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;

SET @stmt := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'rag_files' AND COLUMN_NAME = 'external_uploaded_at'
    ),
    'ALTER TABLE rag_files DROP COLUMN external_uploaded_at',
    'SELECT 1'
  )
);

PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;

SET @stmt := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM INFORMATION_SCHEMA.STATISTICS
      WHERE TABLE_SCHEMA = @db
        AND TABLE_NAME = 'rag_provider_file_uploads'
        AND INDEX_NAME = 'uq_rag_provider_file_uploads_provider_external_file'
    ),
    'SELECT 1',
    'ALTER TABLE rag_provider_file_uploads ADD UNIQUE KEY uq_rag_provider_file_uploads_provider_external_file (provider_id, external_file_id)'
  )
);

PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;
