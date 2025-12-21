SET @db := DATABASE();

SET @stmt := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'rag_files' AND COLUMN_NAME = 'chunking_strategy'
    ),
    'SELECT 1',
    'ALTER TABLE rag_files ADD COLUMN chunking_strategy JSON NULL'
  )
);

PREPARE s FROM @stmt;
EXECUTE s;
DEALLOCATE PREPARE s;
