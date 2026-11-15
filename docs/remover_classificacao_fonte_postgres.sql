-- Migração para PostgreSQL. Execute após iniciar a nova versão do JurisHome.
-- Antes do deploy, permita NULL na coluna antiga se ela existir:
-- ALTER TABLE public.conteudos ALTER COLUMN tipo_fonte DROP NOT NULL;
-- Essa etapa permite que a versão nova grave matérias durante a transição.
-- Faça um backup antes da limpeza definitiva.
BEGIN;
SET LOCAL lock_timeout = '5s';

ALTER TABLE public.conteudos DROP COLUMN IF EXISTS tipo_fonte;
DROP TYPE IF EXISTS public.tipofonte;

COMMIT;
