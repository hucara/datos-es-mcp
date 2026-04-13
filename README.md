# datos-es MCP Server

[![Licencia: MIT](https://img.shields.io/badge/Licencia-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Servidor [MCP (Model Context Protocol)](https://modelcontextprotocol.io) que permite a los asistentes de IA (Claude, ChatGPT, Gemini, etc.) consultar, explorar y analizar datos del ecosistema de datos abiertos de España directamente desde la conversación.

En lugar de navegar manualmente por portales gubernamentales, puedes simplemente preguntar cosas como «¿Cuál es la tasa de paro según el INE?», «¿Cuánto gasta España en sanidad respecto a la media europea?» o «¿Cuál es el ratio cotizantes/pensionistas de la Seguridad Social?» y obtener respuestas inmediatas respaldadas por fuentes oficiales.

Incluye una herramienta especializada de **verificación de afirmaciones políticas** (`verify_claim`) que enruta cualquier declaración económica o política a las fuentes de datos autorizadas y genera un plan de verificación paso a paso.

Este es un proyecto inspirado por el trabajo que puedes ver en:

* https://github.com/datagouv/datagouv-mcp
* https://github.com/AlbertoUAH/datos-gob-es-mcp

¡Dales un vistazo y apóyales!

---

## 🌐 Conecta tu asistente de IA

Si tienes el servidor en ejecución, usa el endpoint `/mcp`. A continuación encontrarás la configuración para los clientes más habituales.

[Claude Code](#claude-code) | [Claude Desktop](#claude-desktop) | [Cursor](#cursor) | [VS Code](#vs-code) | [Windsurf](#windsurf) | [OpenCode](#opencode)

### Claude Code

```shell
claude mcp add --transport http datos-es http://127.0.0.1:8000/mcp
```

### Claude Desktop

Añade lo siguiente al fichero de configuración de Claude Desktop:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "datos-es": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/ruta/a/datos-es-mcp",
        "python",
        "main.py"
      ],
      "env": {
        "AEMET_API_KEY": "tu_clave_aqui"
      }
    }
  }
}
```

O si tienes el servidor ya levantado como HTTP:

```json
{
  "mcpServers": {
    "datos-es": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://127.0.0.1:8000/mcp"
      ]
    }
  }
}
```

### Cursor

1. Abre la configuración de Cursor
2. Busca «MCP» o «Model Context Protocol»
3. Añade el servidor con la siguiente configuración:

```json
{
  "mcpServers": {
    "datos-es": {
      "url": "http://127.0.0.1:8000/mcp",
      "transport": "http"
    }
  }
}
```

### VS Code

Añade lo siguiente al fichero `mcp.json` de VS Code:
- **macOS**: `~/Library/Application Support/Code/User/mcp.json`
- **Windows**: `%APPDATA%\Code\User\mcp.json`
- **Linux**: `~/.config/Code/User/mcp.json`

Puedes abrirlo con el comando **MCP: Open User Configuration** desde la paleta de comandos.

```json
{
  "servers": {
    "datos-es": {
      "url": "http://127.0.0.1:8000/mcp",
      "type": "http"
    }
  }
}
```

### Windsurf

Añade lo siguiente a `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "datos-es": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://127.0.0.1:8000/mcp"
      ]
    }
  }
}
```

### OpenCode

Añade al fichero `opencode.json` (p.ej. `~/.config/opencode/opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "datos-es": {
      "type": "remote",
      "url": "http://127.0.0.1:8000/mcp",
      "enabled": true
    }
  }
}
```

---

## 🖥️ Ejecución local

### Requisitos previos

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (gestor de paquetes recomendado)
- Clave API de AEMET (gratuita) para las herramientas meteorológicas — [solicítala aquí](https://opendata.aemet.es/centrodedescargas/inicio)

### 🐳 Con Docker (recomendado)

```shell
git clone <url-del-repo>
cd datos-es-mcp

# Copia y configura las variables de entorno
cp .env.example .env
# Edita .env y añade tu AEMET_API_KEY

# Inicia el servidor
docker compose up -d

# Comprueba que funciona
curl http://localhost:8000/health

# Detiene el servidor
docker compose down
```

### ⚙️ Instalación manual

1. **Instala las dependencias**
   ```shell
   uv sync
   ```

2. **Prepara el fichero de entorno**
   ```shell
   cp .env.example .env
   ```
   Edita `.env` y configura al menos:
   ```
   AEMET_API_KEY=tu_clave_de_aemet
   MCP_HOST=127.0.0.1
   MCP_PORT=8000
   MCP_ENV=local
   LOG_LEVEL=INFO
   ```
   Carga las variables:
   ```shell
   set -a && source .env && set +a
   ```

3. **Arranca el servidor**
   ```shell
   uv run python main.py
   ```

El servidor arranca en `http://localhost:8000`. El endpoint MCP está en `/mcp`.

Comprobación de salud: `curl http://localhost:8000/health`

---

## 🚚 Transporte

El servidor está construido con el [SDK oficial de Python para MCP](https://github.com/modelcontextprotocol/python-sdk) y usa exclusivamente el transporte **Streamable HTTP**.

**STDIO y SSE no están soportados.**

Endpoints disponibles:
- `POST /mcp` — mensajes JSON-RPC (cliente → servidor)
- `GET /health` — sonda de salud JSON (`{"status":"ok","version":"...","uptime_since":"..."}`)

---

## 🛠️ Herramientas disponibles (25)

### Catálogo nacional — datos.gob.es

| Herramienta | Descripción | Parámetros clave |
|---|---|---|
| `search_datasets` | Busca en los +90.000 datasets de datos.gob.es por palabras clave, tema NTI, organismo o formato. Acepta nombres comunes de institución («INE», «Ministerio de Sanidad») además de slugs CKAN. | `query`, `theme`, `publisher`, `format`, `page` |
| `get_dataset_info` | Metadatos completos de un dataset: organismo, licencia, cobertura geográfica, frecuencia de actualización y lista de distribuciones. | `dataset_id` |
| `list_dataset_resources` | Lista todos los ficheros descargables de un dataset con URL, formato, tamaño y fecha. Con `include_data=True` descarga y previsualiza CSV/JSON directamente (hasta `max_file_size_mb`, por defecto 10 MB). | `dataset_id`, `include_data`, `max_file_size_mb` |

> Flujo típico: `search_datasets` → `get_dataset_info` → `list_dataset_resources`

### INE — Instituto Nacional de Estadística

| Herramienta | Descripción | Parámetros clave |
|---|---|---|
| `get_ine_operations` | Lista las operaciones estadísticas del INE (IPC, EPA, PIB, Padrón, nacimientos…). Resultados servidos desde caché de 24 h tras la primera llamada. | `search`, `page` |
| `query_ine_data` | Obtiene series temporales de cualquier tabla o serie del INE. Tres modos: listar tablas de una operación, descargar tabla completa, o consultar serie específica. | `operation_code`, `table_id`, `series_code`, `last_n_periods`, `date_range` |

> Flujo recomendado: `get_ine_operations` → `query_ine_data(operation_code=...)` → `query_ine_data(table_id=...)`

### Banco de España

| Herramienta | Descripción | Parámetros clave |
|---|---|---|
| `get_bde_series` | Series financieras del Banco de España: tipos BCE, EURIBOR, tipos de cambio, crédito bancario, agregados monetarios y balanza de pagos. | `series_codes`, `time_range` (`30M`/`60M`/`MAX`/año), `latest_only` |

### AEMET — Meteorología

| Herramienta | Descripción | Parámetros clave |
|---|---|---|
| `get_weather_forecast` | Predicción de varios días para cualquier municipio (por código INE de 5 dígitos o por nombre). Temperatura, precipitación, viento y estado del cielo. | `municipality_code`, `detail` (`daily`/`hourly`) |
| `get_weather_observations` | Observaciones actuales de las estaciones AEMET: temperatura, humedad, viento, presión y precipitación. | `station_id` (omitir = todas) |

### BOE — Boletín Oficial del Estado y Legislación

| Herramienta | Descripción | Parámetros clave |
|---|---|---|
| `get_boe_summary` | Resumen diario del BOE o BORME: secciones, departamentos e identificadores de los documentos publicados. | `date` (AAAAMMDD), `gazette` (`BOE`/`BORME`) |
| `search_legislation` | Busca en la legislación consolidada por palabras clave o rango de fechas. Devuelve la norma, departamento y estado de consolidación. | `query`, `from_date`, `to_date`, `limit` |

### Contratación pública

| Herramienta | Descripción | Parámetros clave |
|---|---|---|
| `search_public_contracts` | Licitaciones y contratos en PLACE (plataforma nacional). Modo `datasets` para históricos en bulk; modo `feed` para avisos recientes. | `query`, `source` (`datasets`/`feed`) |
| `search_regional_contracts` | Contratación en Madrid, Cataluña y Valencia. Consulta primero el portal regional nativo (CKAN) y recurre a datos.gob.es si es necesario. | `query`, `region` (`madrid`/`cataluña`/`valencia`/`all`), `page` |

### Empleo

| Herramienta | Descripción | Parámetros clave |
|---|---|---|
| `get_employment_stats` | Estadísticas de empleo del SEPE: paro registrado, contratos y demandantes, con desglose por provincia, sector, edad y sexo. | `stat_type` (`registered_unemployment`/`contracts`/`job_seekers`), `period`, `province` |

### Transporte

| Herramienta | Descripción | Parámetros clave |
|---|---|---|
| `get_renfe_data` | Datos abiertos de Renfe vía data.renfe.com (CKAN): horarios GTFS, estaciones y posiciones en tiempo real. | `data_type` (`schedules`/`stations`/`realtime`), `service_type` (`AVE`/`MD`/`cercanias`) |
| `get_traffic_stats` | Estadísticas de tráfico de la DGT: siniestralidad vial, víctimas, parque de vehículos, matriculaciones (EV vs ICE), permisos de conducción y controles de alcoholemia. | `stat_type` (`accidentes`/`victimas`/`parque_vehiculos`/`matriculaciones`/`carnet`/`alcoholemia`/`velocidad`), `period` |

### Energía y mercados

| Herramienta | Descripción | Parámetros clave |
|---|---|---|
| `get_energy_data` | Datos de Red Eléctrica (REData): mix de generación, capacidad instalada, balance energético, demanda y precios del mercado mayorista. | `data_type` (`generation_mix`/`installed_capacity`/`balance`/`demand`/`market_prices`), `start_date`, `end_date`, `time_trunc` |
| `get_cnmc_data` | Datos regulados de la CNMC vía data.cnmc.es (CKAN): electricidad, gas, telecomunicaciones, correos y mercados de competencia. | `sector` (`electricity`/`gas`/`telecom`/`postal`/`audiovisual`/`competition`), `indicator`, `period` |

### Hacienda y fiscalidad

| Herramienta | Descripción | Parámetros clave |
|---|---|---|
| `get_aeat_stats` | Estadísticas fiscales de la Agencia Tributaria: anuario estadístico (IRPF, IVA, Patrimonio, Sociedades) e informes de recaudación. | `stat_type` (`anuario_estadistico`/`recaudacion`/`irpf`/`iva`/`sociedades`), `query`, `page` |

### Sanidad, educación y servicios públicos

| Herramienta | Fuente principal | Descripción | `stat_type` disponibles |
|---|---|---|---|
| `get_health_stats` | Ministerio de Sanidad / SNS | Gasto sanitario, camas hospitalarias, profesionales sanitarios, listas de espera, mortalidad, vacunación, encuesta nacional de salud. | `gasto_sanitario`, `camas_hospitalarias`, `profesionales`, `listas_espera`, `mortalidad`, `enfermedades`, `salud_mental`, `vacunacion`, `encuesta_salud` |
| `get_education_stats` | Ministerio de Educación / MEFP | Abandono escolar, matriculados, universitarios, profesorado, becas, gasto educativo, FP, resultados PISA. | `abandono_escolar`, `matriculados`, `universitarios`, `profesorado`, `becas`, `gasto_educativo`, `fp`, `pisa` |
| `get_housing_stats` | Ministerio de Vivienda + INE | Precios de vivienda (IPV), alquileres, hipotecas, visados de construcción, parque de viviendas, vivienda protegida, ejecuciones hipotecarias. | `precios_vivienda`, `alquileres`, `hipotecas`, `construccion`, `parque_viviendas`, `vivienda_protegida`, `ejecuciones_hipotecarias` |
| `get_social_security_stats` | INSS / Min. Inclusión | Pensiones, cotizantes, ratio sostenibilidad, prestaciones por desempleo, incapacidad temporal, accidentes laborales, afiliados extranjeros. | `pensiones`, `cotizantes`, `ratio_sostenibilidad`, `prestaciones_desempleo`, `incapacidad`, `accidentes_laborales`, `inmigracion` |
| `get_traffic_stats` | DGT | Siniestralidad vial, víctimas, parque de vehículos, matriculaciones, permisos de conducción, alcoholemia, velocidad. | `accidentes`, `victimas`, `parque_vehiculos`, `matriculaciones`, `carnet`, `alcoholemia`, `velocidad` |
| `get_justice_stats` | Min. Justicia / CGPJ | Criminalidad, condenas, población penitenciaria, carga judicial, violencia de género, justicia de menores, corrupción. | `criminalidad`, `condenas`, `presos`, `juzgados`, `violencia_genero`, `menores`, `corrupcion` |

Todas las herramientas de esta sección aceptan además `period` (año o rango, p.ej. `"2023"`, `"2020-2023"`) y `custom_query` para búsquedas libres.

### Comparativas europeas

| Herramienta | Descripción | Parámetros clave |
|---|---|---|
| `get_eurostat_data` | Datos de Eurostat para comparar España con la UE-27: PIB, inflación HICP, desempleo, vivienda, renovables, deuda pública, salarios, desigualdad. | `topic`, `geo` (por defecto `ES,EU27_2020`), `since_year`, `until_year`, `dataset_code` (para `topic="custom"`) |

Temas disponibles: `gdp_growth`, `gdp_per_capita`, `inflation_hicp`, `inflation_annual`, `unemployment`, `employment_rate`, `house_prices`, `renewable_share`, `electricity_prices_households`, `electricity_prices_industry`, `government_debt`, `government_deficit`, `wages`, `poverty_inequality`, `fossil_fuel_imports`

### Verificación de afirmaciones

| Herramienta | Descripción | Parámetros obligatorios |
|---|---|---|
| `verify_claim` | Clasifica una afirmación política o económica y devuelve un plan de verificación estructurado: qué herramientas llamar, con qué argumentos y en qué orden. No ejecuta las consultas directamente. | `claim_normalizado`, `fecha`, `afirmado_por`, `ambito_geografico`, `ambito_tematico`, `tipo_claim` |

#### Documentación detallada de `verify_claim`

El enrutamiento combina cuatro señales:
- **`claim_normalizado`**: coincidencia de palabras clave sobre el texto
- **`ambito_tematico`**: taxonomía temática (captura casos que los keywords no detectan)
- **`entidad_mencionada`** + **`fuente_citada`**: sugerencias específicas por institución
- **`ambito_geografico`**: añade portales regionales para afirmaciones sub-nacionales

**Parámetros obligatorios:**

| Parámetro | Descripción |
|-----------|-------------|
| `claim_normalizado` | La afirmación en español normalizado. Los nombres y contexto deben ser explícitos (p.ej. «Santiago Abascal tiene 3 investigaciones» en vez de «Usted tiene 3 investigaciones»). |
| `fecha` | **Siempre requerida.** Fecha en que se realizó la afirmación (`AAAA`, `AAAA-MM` o `AAAA-MM-DD`). Es el límite superior duro para todas las consultas: no se buscarán datos publicados después de esta fecha. **No confundir con `periodo_temporal`**. |
| `afirmado_por` | Quién realizó la afirmación. Ejemplo: `"Pedro Sánchez"`, `"Partido Popular"`. |
| `ambito_geografico` | Alcance geográfico. Valores canónicos: 17 CCAA + `"España"` + `"Europa"` / `"Unión Europea"` + `"Internacional"`. |
| `ambito_tematico` | Categoría temática. Acepta español e inglés: `economía`/`economy`, `sanidad`/`health`, `educación`/`education`, `vivienda`/`housing`, `pensiones`/`pensions`, `trafico`/`traffic`, `criminalidad`/`crime`, `medio_ambiente`/`environment`, `empleo`/`employment`, `demografía`/`demographics`, `fiscalidad`/`taxation`, `banca`/`banking`, `empresas`/`business`, `justicia_y_corrupción`/`corruption`, `presupuestos`/`public_debt`, `contratacion_publica`/`procurement`. |
| `tipo_claim` | Tipo estructural: `estadistica_puntual`, `historico`, `ranking`, `tendencia`, `comparacion`, `proyeccion`. |

**Parámetros secundarios:**

| Parámetro | Descripción |
|-----------|-------------|
| `claim_raw` | Texto verbatim original (con contexto, idioma original, interrupciones). Solo para trazabilidad. |
| `entidad_mencionada` | Institución a la que se refiere la afirmación. Activa sugerencias específicas. Ejemplo: `"INE"`, `"Tribunal de Cuentas"`. |
| `metrica` | La métrica concreta afirmada. Ejemplo: `"tasa de abandono escolar"`. |
| `valor_afirmado` | El valor concreto afirmado. Aparece en el checklist. Ejemplo: `"98%"`, `"más baja de la historia"`. |
| `periodo_temporal` | El período al que se refiere la afirmación — **distinto de `fecha`**. Orienta las consultas pero nunca actúa como límite de datos. Ejemplo: `"2022"`, `"2018-2023"`, `"actual"`. |
| `fuente_citada` | Fuente mencionada por quien hace la afirmación. Ejemplo: `"INE"`, `"No citada"`. |
| `idioma` | Código ISO 639-1 del idioma del `claim_raw` (`es`, `ca`, `gl`, `eu`). |
| `intervention_orden` | Posición en la sesión (base 1). Solo para trazabilidad. |
| `return_data` | Si `true`, incluye una nota sobre la primera fuente recomendada. Por defecto `false`. |

**Estrategias por tipo de afirmación:**

| `tipo_claim` | Estrategia aplicada |
|--------|---------------------|
| `estadistica_puntual` | Localizar el valor oficial exacto y comparar con `valor_afirmado`. |
| `historico` | Buscar el acto legislativo o administrativo en BOE/Diario de Sesiones. |
| `ranking` | Recuperar la serie temporal más larga posible (`since_year="2000"` o `MAX`) para verificar el superlativo. |
| `tendencia` | Obtener la serie completa del período afirmado y calcular dirección y magnitud. |
| `comparacion` | Usar Eurostat para datos armonizados con el mismo año y metodología para todos los países. |
| `proyeccion` | Identificar la institución que generó la proyección y comparar con datos reales si el período ya ha pasado. |

---

## 🔍 Casos de uso

### Verificación de afirmaciones políticas con `verify_claim`

**Afirmación sobre nacimientos (estadística puntual, INE):**
```python
verify_claim(
    claim_normalizado="En España nacieron 328.704 niños en 2022",
    fecha="2025-10-14",
    ambito_geografico="España",
    ambito_tematico="demografía",
    entidad_mencionada="INE",
    metrica="número de nacimientos",
    valor_afirmado="328.704",
    periodo_temporal="2022",
    fuente_citada="INE",
    tipo_claim="estadistica_puntual",
)
# → query_ine_data(operation_code="MNP") limitado a datos anteriores a oct-2025
```

**Afirmación de ranking — abandono escolar:**
```python
verify_claim(
    claim_normalizado="La tasa de abandono escolar es la más baja de la historia de España",
    fecha="2025-10-29",
    ambito_geografico="España",
    ambito_tematico="educación",
    metrica="tasa de abandono escolar temprano",
    valor_afirmado="más baja de la historia",
    periodo_temporal="actual",
    tipo_claim="ranking",
)
# → get_education_stats(stat_type="abandono_escolar")
# → get_eurostat_data(dataset_code="edat_lfse_14", since_year="2000") — serie completa para verificar superlativo
```

**Afirmación sobre pensiones:**
```python
verify_claim(
    claim_normalizado="El ratio cotizantes/pensionistas ha caído por debajo de 2",
    fecha="2026-04-01",
    ambito_geografico="España",
    ambito_tematico="pensiones",
    metrica="ratio cotizantes por pensionista",
    tipo_claim="estadistica_puntual",
)
# → get_social_security_stats(stat_type="ratio_sostenibilidad")
# → get_social_security_stats(stat_type="cotizantes")
```

**Afirmación histórica — voto parlamentario:**
```python
verify_claim(
    claim_normalizado="El Partido Popular votó a favor de establecer el impuesto al sol",
    fecha="2025-11-13",
    ambito_geografico="España",
    ambito_tematico="medio_ambiente",
    entidad_mencionada="Congreso de los Diputados",
    tipo_claim="historico",
)
# → search_legislation(query="impuesto sol autoconsumo energía renovable")
# → get_boe_summary con la fecha del RD correspondiente
```

**Afirmación sobre tejido empresarial regional (Cataluña):**
```python
verify_claim(
    claim_normalizado="Las pymes suponen el 98% del tejido empresarial catalán",
    fecha="2026-02-17",
    claim_raw="el 98 % del teixit empresarial català",
    ambito_geografico="Cataluña",
    ambito_tematico="empresas",
    metrica="porcentaje de pymes sobre total empresas",
    valor_afirmado="98%",
    periodo_temporal="actual",
    idioma="ca",
    tipo_claim="estadistica_puntual",
)
# → search_datasets(query="directorio central empresas DIRCE INE")
# → search_regional_contracts(region="cataluña") — portal regional activado por ambito_geografico
```

### Investigación de datos de ministerios

```
"¿Cuántos médicos por habitante tiene España respecto a la UE?"
→ get_health_stats(stat_type="profesionales")
→ get_eurostat_data("custom", dataset_code="hlth_rs_prshp", geo="ES,EU27_2020")

"¿Cuántos cotizantes hay por pensionista en España?"
→ get_social_security_stats(stat_type="ratio_sostenibilidad")

"¿Cuántos muertos en carretera hubo en 2023?"
→ get_traffic_stats(stat_type="victimas", period="2023")

"¿Ha bajado la tasa de criminalidad en los últimos cinco años?"
→ get_justice_stats(stat_type="criminalidad")

"¿Cuánto ha subido el precio del alquiler en los últimos años?"
→ get_housing_stats(stat_type="alquileres")
→ get_eurostat_data("house_prices", geo="ES,EU27_2020", since_year="2015")
```

### Análisis de gasto público regional

```
"¿Cuánto gasta la Comunidad de Madrid en contratos de informática?"
→ search_regional_contracts(query="servicios informatica", region="madrid")

"Comparar licitaciones de sanidad entre comunidades"
→ search_regional_contracts(query="servicios sanitarios", region="all")
```

### Investigación macroeconómica

```
get_eurostat_data("unemployment", geo="ES,EU27_2020,PT,IT", since_year="2019")
get_bde_series(series_codes="TI_1_2_1,TI_2_12_1", time_range="60M")
query_ine_data(table_id="50902")   # IPC mensual
```

---

## 🗂️ Fuentes de datos

| Institución | Cobertura | Autenticación |
|-------------|-----------|---------------|
| [datos.gob.es](https://datos.gob.es) | +90.000 datasets de todos los organismos públicos | No |
| [INE](https://www.ine.es) | Demografía, IPC, PIB, encuestas de empleo, padrón | No |
| [Banco de España](https://www.bde.es) | Tipos de interés, divisas, crédito, banca, agregados monetarios | No |
| [AEMET](https://opendata.aemet.es) | Predicciones, observaciones y clima histórico | Clave gratuita |
| [BOE](https://www.boe.es) | Boletín Oficial, BORME, legislación consolidada | No |
| [PLACE](https://contrataciondelestado.es) | Licitaciones y contratos del sector público nacional | No |
| [Comunidad de Madrid](https://datos.comunidad.madrid) | Datos abiertos y contratación regional | No |
| [Generalitat de Catalunya](https://analisi.transparenciacatalunya.cat) | Datos abiertos y contratación regional | No |
| [Generalitat Valenciana](https://dadesobertes.gva.es) | Datos abiertos y contratación regional | No |
| [SEPE](https://sede.sepe.gob.es) | Paro registrado y contratos laborales | No |
| [Renfe](https://data.renfe.com) | Horarios, estaciones y posiciones en tiempo real | No |
| [DGT](https://www.dgt.es) | Siniestralidad vial, parque de vehículos, matriculaciones | No |
| [Ministerio de Sanidad / SNS](https://www.sanidad.gob.es) | Gasto sanitario, profesionales, camas, listas de espera, mortalidad | No |
| [Ministerio de Educación / MEFP](https://www.educacionyfp.gob.es) | Abandono escolar, matriculados, becas, gasto educativo | No |
| [Ministerio de Vivienda](https://www.mivau.gob.es) | Precios de vivienda, hipotecas, construcción, desahucios | No |
| [INSS / Min. Seguridad Social](https://www.seg-social.es) | Pensiones, cotizantes, prestaciones por desempleo, incapacidad | No |
| [Ministerio de Justicia / CGPJ](https://www.poderjudicial.es) | Criminalidad, condenas, población penitenciaria, violencia de género | No |
| [Red Eléctrica / REData](https://apidatos.ree.es) | Generación eléctrica, precios y demanda en tiempo real | No |
| [CNMC](https://data.cnmc.es) | Electricidad, gas, telecomunicaciones, competencia | No |
| [AEAT](https://sede.agenciatributaria.gob.es) | Recaudación tributaria, IRPF, IVA, Sociedades | No |
| [Eurostat](https://ec.europa.eu/eurostat) | Estadísticas europeas para comparativas con la UE | No |

---

## 🧪 Tests

### Tests automatizados con pytest

```shell
# Ejecutar todos los tests
uv run pytest

# Con salida detallada
uv run pytest -v

# Ejecutar un fichero concreto
uv run pytest tests/test_ine.py
```

### Pruebas interactivas con MCP Inspector

El [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) oficial permite probar las herramientas de forma interactiva desde el navegador.

Requisitos previos: Node.js con `npx` disponible.

1. Arranca el servidor MCP (ver arriba)
2. En otro terminal, lanza el inspector:
   ```shell
   npx @modelcontextprotocol/inspector --http-url "http://127.0.0.1:${MCP_PORT:-8000}/mcp"
   ```

---

## 🔧 Desarrollo

### Linting y formateo

Este proyecto usa [Ruff](https://astral.sh/ruff/) para linting y formateo, y [ty](https://docs.astral.sh/ty/) para la comprobación de tipos.

```shell
# Lint (incluida ordenación de imports) y formateo
uv run ruff check --fix && uv run ruff format

# Comprobación de tipos
uv run ty check
```

### Hooks de pre-commit

```shell
# Instalar el hook
uv run pre-commit install
```

El hook ejecuta automáticamente antes de cada commit:
- Verificación de sintaxis YAML
- Corrección de fin de fichero y espacios en blanco
- Linting y formateo con Ruff

### Variables de entorno

| Variable | Por defecto | Descripción |
|----------|-------------|-------------|
| `MCP_HOST` | `0.0.0.0` | Host en el que escucha el servidor. Usa `127.0.0.1` en desarrollo local |
| `MCP_PORT` | `8000` | Puerto del servidor HTTP |
| `MCP_ENV` | `local` | Nombre del entorno reportado a Sentry (`local`, `staging`, `production`) |
| `LOG_LEVEL` | `INFO` | Nivel de log de Python (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_FORMAT` | `text` | Formato de logs: `text` (legible por humanos) o `json` (para Loki/Datadog/CloudWatch) |
| `AEMET_API_KEY` | — | **Requerida** para las herramientas meteorológicas. [Solicitar aquí](https://opendata.aemet.es/centrodedescargas/inicio) |
| `SENTRY_DSN` | — | DSN de Sentry para monitorización de errores (desactivado si está vacío) |
| `SENTRY_SAMPLE_RATE` | `1.0` | Tasa de muestreo de Sentry (float `0.0`–`1.0`) |
| `MATOMO_URL` | — | URL de la instancia Matomo para analíticas (desactivado si está vacío) |
| `MATOMO_SITE_ID` | — | ID del sitio en Matomo |
| `MATOMO_AUTH_TOKEN` | — | Token de autenticación de Matomo |

### Estructura del proyecto

```
datos-es-mcp/
├── main.py                          # App ASGI FastMCP + endpoint /health
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── helpers/
│   ├── http.py                      # Fetch con retry y backoff exponencial (compartido)
│   ├── cache.py                     # Caché de metadatos con TTL de 24 h
│   ├── publishers.py                # Diccionario de publishers conocidos (60+ aliases)
│   ├── env_config.py                # URLs de APIs por entorno
│   ├── datos_gob_es_client.py       # API CKAN de datos.gob.es
│   ├── ine_client.py                # API JSON del INE (Tempus3)
│   ├── bde_client.py                # API de estadísticas del Banco de España
│   ├── aemet_client.py              # AEMET OpenData (fetch en dos pasos)
│   ├── boe_client.py                # API REST del BOE/BORME/Legislación
│   ├── place_client.py              # Feed ATOM de PLACE + datos.gob.es
│   ├── regional_contracts_client.py # Portales Madrid / Cataluña / Valencia
│   ├── sepe_client.py               # Datos de empleo del SEPE
│   ├── renfe_client.py              # Portal de datos abiertos de Renfe
│   ├── cnmc_client.py               # Portal CKAN de la CNMC
│   ├── redata_client.py             # API REData de Red Eléctrica
│   ├── eurostat_client.py           # API de Eurostat (formato JSON-stat)
│   ├── aeat_client.py               # Datasets fiscales de la AEAT
│   ├── ministerios_client.py        # Cliente compartido para los 6 ministerios
│   ├── logging.py                   # Logging configurable (text/JSON)
│   ├── sentry.py
│   ├── matomo.py
│   └── user_agent.py
└── tools/
    ├── __init__.py                  # register_tools(mcp) — 25 herramientas
    ├── search_datasets.py
    ├── get_dataset_info.py
    ├── list_dataset_resources.py    # include_data=True para preview CSV/JSON
    ├── get_ine_operations.py        # Usa caché de 24 h
    ├── query_ine_data.py
    ├── get_bde_series.py
    ├── get_weather_forecast.py
    ├── get_weather_observations.py
    ├── get_boe_summary.py
    ├── search_legislation.py
    ├── search_public_contracts.py
    ├── search_regional_contracts.py
    ├── get_employment_stats.py
    ├── get_renfe_data.py
    ├── get_cnmc_data.py
    ├── get_energy_data.py
    ├── get_eurostat_data.py
    ├── get_aeat_stats.py
    ├── get_health_stats.py          # Ministerio de Sanidad / SNS
    ├── get_education_stats.py       # Ministerio de Educación / MEFP
    ├── get_housing_stats.py         # Ministerio de Vivienda + INE
    ├── get_traffic_stats.py         # DGT
    ├── get_social_security_stats.py # INSS / Seguridad Social
    ├── get_justice_stats.py         # Min. Justicia / CGPJ
    └── verify_claim.py
```

---

## 🤝 Contribuciones

Actualmente no se buscan contribuciones. Si quieres, siempre puedes crear un fork.

---

## 📄 Licencia

Este proyecto está licenciado bajo la Licencia MIT — consulta el fichero [LICENSE](LICENSE) para más detalles.
