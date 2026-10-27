-- =====================================================================================
-- 00_criar_banco.sql — criação do banco independente do projeto (executar UMA vez)
-- Requer superusuário (ex.: postgres). Não sobrescreve banco existente.
--
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h localhost -U postgres -d postgres `
--       -v owner=gis_portfolio -f sql\00_criar_banco.sql
--
-- Depois, acrescente ao seu pgpass (%APPDATA%\postgresql\pgpass.conf) uma linha:
--   localhost:5432:sevilla_oferta_bus:gis_portfolio:<sua senha>
-- =====================================================================================
\set ON_ERROR_STOP on
\if :{?owner}
\else
  \set owner gis_portfolio
\endif

SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_database WHERE datname = 'sevilla_oferta_bus')
            THEN 'AVISO: banco sevilla_oferta_bus ja existe — nada sera recriado'
            ELSE 'Criando banco sevilla_oferta_bus' END AS status;

SELECT format('CREATE DATABASE sevilla_oferta_bus OWNER %I ENCODING ''UTF8'' TEMPLATE template0', :'owner')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'sevilla_oferta_bus')
\gexec

\connect sevilla_oferta_bus
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT postgis_full_version();
