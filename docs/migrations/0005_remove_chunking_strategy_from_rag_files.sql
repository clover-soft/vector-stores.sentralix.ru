-- Удаление поля chunking_strategy из rag_files
-- Миграция: 0005_remove_chunking_strategy_from_rag_files.sql

-- Удаляем поле chunking_strategy из rag_files (теперь хранится в rag_index_files)
ALTER TABLE rag_files 
DROP COLUMN IF EXISTS chunking_strategy;
