-- Добавление поля external_id в rag_index_files
-- Миграция: 0004_add_external_id_and_chunking_to_rag_index_files.sql

ALTER TABLE rag_index_files 
ADD COLUMN external_id VARCHAR(256) NULL;

-- Создание индекса для external_id для ускорения запросов
CREATE INDEX idx_rag_index_files_external_id ON rag_index_files(external_id);
