-- Добавление полей external_id и chunking_strategy в rag_index_files
-- Миграция: 0004_add_external_id_and_chunking_to_rag_index_files.sql

-- Добавляем поле external_id
ALTER TABLE rag_index_files 
ADD COLUMN external_id VARCHAR(256) NULL;

-- Создаем индекс для external_id для ускорения запросов
CREATE INDEX idx_rag_index_files_external_id ON rag_index_files(external_id);

-- Добавляем поле chunking_strategy (стратегия чанков в контексте индекса)
ALTER TABLE rag_index_files 
ADD COLUMN chunking_strategy JSON NULL;
