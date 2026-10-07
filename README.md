# Pipeline ETL de exportaciones del NEA

Proyecto de análisis de datos que extrae series oficiales de exportaciones de
Chaco, Corrientes, Formosa y Misiones, las transforma en un dataset analítico y
valida y guarda los resultados.

## Qué hace el pipeline

El proceso tiene tres etapas:

1. **Extrae** series anuales desde la API de Series de Tiempo de datos.gob.ar y
   conserva las respuestas originales en `data/raw/`.
2. **Transforma** los datos del formato ancho de la API a una tabla larga con
   una fila por año, provincia y destino. Agrega región geoeconómica,
   participación sobre el total provincial, variación interanual, década,
   ranking por destino y datos de exportaciones por rubro.
3. **Valida y guarda** el dataset: comprueba cantidad de filas, columnas,
   unicidad, rangos y cobertura; después escribe un CSV, un resumen JSON y un
   registro de la corrida.

La salida principal es `data/processed/exportaciones_nea.csv`, con 13 columnas,
1.408 filas esperadas y datos del período 1993–2024. También se generan
`data/processed/resumen.json` y archivos de ejecución en `logs/`.

## Instalación y ejecución

Se requiere **Python 3.8 o superior**. El proyecto usa únicamente la biblioteca
estándar de Python, por lo que no hace falta instalar paquetes adicionales.

Desde la carpeta raíz del proyecto, podés crear y activar un entorno virtual
(opcional):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Ejecutá el pipeline con conexión a internet:

```powershell
python src/main.py
```

La primera ejecución descarga los datos y los guarda en `data/raw/`. Para
volver a procesar esas copias sin conectarte a internet:

```powershell
python src/main.py --sin-internet
```

Para correr las pruebas de transformación:

```powershell
python tests/test_transform.py
```

## Origen de los datos

Los datos provienen de series del **INDEC** publicadas en la [API de Series de
Tiempo de datos.gob.ar](https://apis.datos.gob.ar/series/api/). Se usan los
datasets **357.1** (exportaciones por provincia y país de destino) y **350.1**
(exportaciones por provincia y rubro). El pipeline consulta las cuatro
provincias del NEA y trabaja con valores expresados en millones de dólares.

## Una observación del CSV

En la serie del total provincial de Corrientes se observa un salto marcado:
pasó de **217,41 millones de USD en 2019** a **585,82 millones en 2020**. En
2021 el valor volvió a **297,56 millones**. Es una variación llamativa en los
datos y puede servir como punto de partida para investigar qué productos o
destinos explican ese año; por sí sola, esta observación no identifica la causa.

## Estructura

```text
src/
  config.py       IDs de series, rutas y parámetros del pipeline
  extract.py      Descarga y lectura de datos crudos
  transform.py   Transformaciones y construcción del dataset analítico
  load.py         Controles de calidad y persistencia de resultados
  main.py         Orquestación de las etapas
tests/
  test_transform.py
data/
  raw/            Respuestas originales de la API
  processed/      CSV y resumen JSON
logs/             Registros de ejecución
```
