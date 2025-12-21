-- Добавление поля external_id и удаление chunking_strategy в rag_index_files
-- Миграция: 0004_add_external_id_and_chunking_to_rag_index_files.sql

-- Добавляем поле external_id
ALTER TABLE rag_index_files 
ADD COLUMN external_id VARCHAR(256) NULL;

-- Создаем индекс для external_id для ускорения запросов
CREATE INDEX idx_rag_index_files_external_id ON rag_index_files(external_id);

-- Удаляем поле chunking_strategy (теперь хранится в rag_files)
ALTER TABLE rag_index_files 
DROP COLUMN IF EXISTS chunking_strategy;
