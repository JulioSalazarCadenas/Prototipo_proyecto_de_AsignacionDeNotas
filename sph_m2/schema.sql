-- SPH · Esquema relacional final (3FN). Dialecto: SQLite (probado con 3.45.1; usa índice sobre expresión y triggers; claves foráneas activadas con PRAGMA).
-- Cambios respecto del DER de M2 (Ajuste 3 del autodiagnóstico):
--   1) parametro: unicidad que trata el id_regla nulo (COALESCE) y valor con tipo explícito y CHECK.
--   2) cambio_sesion: bitácora inmutable (sin CASCADE; triggers que impiden UPDATE y DELETE).
--   3) Una sola fuente de horas máximas: dedicacion.horas_maximas (Parametros las lee de aquí).
--   4) sesion.codigo: identificador legible (S01...) para trazar con los documentos y los logs.
CREATE TABLE semestre (
  id_semestre  TEXT PRIMARY KEY,
  fecha_inicio TEXT NOT NULL,
  fecha_fin    TEXT NOT NULL,
  CHECK (fecha_fin > fecha_inicio)
);
CREATE TABLE usuario (
  id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre     TEXT NOT NULL,
  correo     TEXT NOT NULL UNIQUE,
  rol        TEXT NOT NULL CHECK (rol IN ('COORDINADOR','CONSULTA','ADMIN'))
);
CREATE TABLE curso (
  id_curso TEXT PRIMARY KEY,
  nombre   TEXT NOT NULL
);
CREATE TABLE grupo (
  id_grupo TEXT PRIMARY KEY
);
CREATE TABLE dedicacion (
  id_dedicacion INTEGER PRIMARY KEY,
  nombre        TEXT NOT NULL UNIQUE,
  horas_maximas INTEGER NOT NULL CHECK (horas_maximas > 0)
);
CREATE TABLE especialidad (
  id_especialidad INTEGER PRIMARY KEY,
  nombre          TEXT NOT NULL UNIQUE
);
CREATE TABLE docente (
  id_docente      TEXT PRIMARY KEY,
  nombre          TEXT NOT NULL,
  id_dedicacion   INTEGER NOT NULL REFERENCES dedicacion(id_dedicacion),
  id_especialidad INTEGER REFERENCES especialidad(id_especialidad)
);
CREATE TABLE disponibilidad_docente (
  id_disponibilidad INTEGER PRIMARY KEY AUTOINCREMENT,
  id_docente  TEXT NOT NULL REFERENCES docente(id_docente) ON DELETE CASCADE,
  dia         INTEGER NOT NULL CHECK (dia BETWEEN 1 AND 6),
  hora_inicio INTEGER NOT NULL CHECK (hora_inicio BETWEEN 0 AND 23),
  hora_fin    INTEGER NOT NULL CHECK (hora_fin BETWEEN 1 AND 24),
  CHECK (hora_fin > hora_inicio)
);
CREATE TABLE aula (
  id_aula   TEXT PRIMARY KEY,
  nombre    TEXT NOT NULL,
  capacidad INTEGER NOT NULL CHECK (capacidad > 0),
  accesible INTEGER NOT NULL DEFAULT 0 CHECK (accesible IN (0,1))
);
CREATE TABLE tecnologia (
  id_tecnologia INTEGER PRIMARY KEY,
  nombre        TEXT NOT NULL UNIQUE
);
CREATE TABLE aula_tecnologia (
  id_aula       TEXT NOT NULL REFERENCES aula(id_aula) ON DELETE CASCADE,
  id_tecnologia INTEGER NOT NULL REFERENCES tecnologia(id_tecnologia),
  PRIMARY KEY (id_aula, id_tecnologia)
);
CREATE TABLE oferta (
  id_oferta     INTEGER PRIMARY KEY AUTOINCREMENT,
  id_semestre   TEXT NOT NULL REFERENCES semestre(id_semestre),
  id_curso      TEXT NOT NULL REFERENCES curso(id_curso),
  id_grupo      TEXT NOT NULL REFERENCES grupo(id_grupo),
  cupo_esperado INTEGER NOT NULL CHECK (cupo_esperado > 0),
  UNIQUE (id_semestre, id_curso, id_grupo)
);
CREATE TABLE oferta_tecnologia (
  id_oferta     INTEGER NOT NULL REFERENCES oferta(id_oferta) ON DELETE CASCADE,
  id_tecnologia INTEGER NOT NULL REFERENCES tecnologia(id_tecnologia),
  PRIMARY KEY (id_oferta, id_tecnologia)
);
CREATE TABLE propuesta (
  id_propuesta        INTEGER PRIMARY KEY AUTOINCREMENT,
  id_semestre         TEXT NOT NULL REFERENCES semestre(id_semestre),
  id_usuario          INTEGER NOT NULL REFERENCES usuario(id_usuario),
  id_propuesta_origen INTEGER REFERENCES propuesta(id_propuesta),
  nombre              TEXT NOT NULL,
  estado              TEXT NOT NULL DEFAULT 'BORRADOR' CHECK (estado IN ('BORRADOR','VALIDADA','APROBADA','ARCHIVADA')),
  creada_en           TEXT NOT NULL
);
CREATE TABLE sesion (
  id_sesion    INTEGER PRIMARY KEY AUTOINCREMENT,
  id_propuesta INTEGER NOT NULL REFERENCES propuesta(id_propuesta),
  codigo       TEXT    NOT NULL,
  id_oferta    INTEGER NOT NULL REFERENCES oferta(id_oferta),
  id_docente   TEXT    NOT NULL REFERENCES docente(id_docente),
  id_aula      TEXT    NOT NULL REFERENCES aula(id_aula),
  dia          INTEGER NOT NULL CHECK (dia BETWEEN 1 AND 6),
  hora_inicio  INTEGER NOT NULL CHECK (hora_inicio BETWEEN 0 AND 23),
  hora_fin     INTEGER NOT NULL CHECK (hora_fin BETWEEN 1 AND 24),
  CHECK (hora_fin > hora_inicio),
  UNIQUE (id_propuesta, codigo)
  -- Sin restricción de exclusión (docente/aula/grupo): la propuesta de partida PUEDE contener
  -- conflictos. El bloqueo de choques ocurre en la capa de servicio (ServicioHorarios.mover).
);
CREATE INDEX ix_sesion_docente_dia ON sesion (id_propuesta, id_docente, dia);
CREATE INDEX ix_sesion_aula_dia    ON sesion (id_propuesta, id_aula, dia);
CREATE TABLE regla (
  id_regla    TEXT PRIMARY KEY,
  tipo        TEXT NOT NULL CHECK (tipo IN ('DURA','BLANDA')),
  nombre      TEXT NOT NULL,
  descripcion TEXT NOT NULL,
  activa      INTEGER NOT NULL DEFAULT 1 CHECK (activa IN (0,1))
);
CREATE TABLE parametro (
  id_parametro      INTEGER PRIMARY KEY AUTOINCREMENT,
  id_regla          TEXT REFERENCES regla(id_regla),      -- NULL = parámetro global
  id_semestre_desde TEXT NOT NULL REFERENCES semestre(id_semestre),
  clave             TEXT NOT NULL,
  tipo_valor        TEXT NOT NULL CHECK (tipo_valor IN ('ENTERO','REAL','TEXTO')),
  valor             TEXT NOT NULL,
  CHECK (tipo_valor <> 'ENTERO' OR (valor <> '' AND valor NOT GLOB '*[^0-9]*')),
  CHECK (tipo_valor <> 'REAL'   OR (valor <> '' AND valor NOT GLOB '*[^0-9.]*'))
);
CREATE UNIQUE INDEX ux_parametro ON parametro (COALESCE(id_regla, ''), clave, id_semestre_desde);
CREATE TABLE cambio_sesion (
  id_cambio       INTEGER PRIMARY KEY AUTOINCREMENT,
  id_propuesta    INTEGER NOT NULL REFERENCES propuesta(id_propuesta),
  id_sesion       INTEGER NOT NULL REFERENCES sesion(id_sesion),
  id_usuario      INTEGER NOT NULL REFERENCES usuario(id_usuario),
  id_regla_origen TEXT REFERENCES regla(id_regla),
  origen          TEXT NOT NULL CHECK (origen IN ('MANUAL','SUGERENCIA','DESHACER')),
  criterio        TEXT,
  dia_ant INTEGER NOT NULL, hora_ini_ant INTEGER NOT NULL, hora_fin_ant INTEGER NOT NULL,
  id_aula_ant TEXT NOT NULL REFERENCES aula(id_aula), id_docente_ant TEXT NOT NULL REFERENCES docente(id_docente),
  dia_nue INTEGER NOT NULL, hora_ini_nue INTEGER NOT NULL, hora_fin_nue INTEGER NOT NULL,
  id_aula_nue TEXT NOT NULL REFERENCES aula(id_aula), id_docente_nue TEXT NOT NULL REFERENCES docente(id_docente),
  deshace_id      INTEGER REFERENCES cambio_sesion(id_cambio),
  realizado_en    TEXT NOT NULL
);
CREATE INDEX ix_cambio_propuesta ON cambio_sesion (id_propuesta, id_cambio);
CREATE TRIGGER tg_cambio_no_update BEFORE UPDATE ON cambio_sesion
BEGIN SELECT RAISE(ABORT, 'La bitácora de cambios es inmutable'); END;
CREATE TRIGGER tg_cambio_no_delete BEFORE DELETE ON cambio_sesion
BEGIN SELECT RAISE(ABORT, 'La bitácora de cambios es inmutable'); END;
