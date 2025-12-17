SET @db := DATABASE();

SET @stmt := (
  SELECT IF(
    EXISTS(
      SELECT 1
      FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'rag_indexes' AND COLUMN_NAME = 'chunking_strategy'
    ),
    'ALTER TABLE rag_indexes DROP COLUMN chunking_strategy',
    'SELECT 1'
  )
);
PREPARE s FROM @stmt; EXECUTE s; DEALLOCATE PREPARE s;
