"""
LOAD — Quality checks y persistencia   *** PARCIALMENTE RESUELTO ***
=====================================================================

Dos responsabilidades, en este orden:

  1. CHEQUEAR: validar el dataset antes de publicarlo. Si algo crítico
     falla, cortamos: mejor no entregar nada que entregar un reporte roto.
  2. GUARDAR: escribir el CSV (para personas), el resumen JSON (para
     programas) y el log (para auditar).

Te dejamos resuelto el guardado del CSV y dos de los quality checks.
Faltan 4 TODOs (9 a 12), todos cortos.

Idempotencia: el CSV y el JSON van en modo "w", así que correr el pipeline
dos veces deja el mismo resultado. El log va en modo "a" porque un log ES
un historial: ahí sí queremos que crezca.
"""

import csv
import json
import logging
import os
from datetime import datetime

import config
from transform import COLUMNAS


# ======================================================================
# QUALITY CHECKS
# ======================================================================
def chequear_cantidad(filas, minimo=None):
    """Comprueba que el conjunto tenga al menos la cantidad mínima de filas.

    Si no se indica ``minimo``, usa el umbral de configuración.
    Devuelve una tupla con el resultado booleano y un mensaje descriptivo.
    """
    if minimo is None:
        minimo = config.MINIMO_FILAS_ESPERADAS
    ok = len(filas) >= minimo
    return ok, f"cantidad: {len(filas)} filas (mínimo esperado {minimo})"


def chequear_columnas(filas):
    """Comprueba que todas las filas respeten el esquema definido en COLUMNAS.

    Devuelve una tupla con el resultado booleano y un mensaje descriptivo.
    """
    esperadas = set(COLUMNAS)
    for fila in filas:
        if set(fila.keys()) != esperadas:
            faltan = esperadas - set(fila.keys())
            return False, f"columnas: una fila no cumple el esquema (faltan {faltan})"
    return True, f"columnas: las {len(COLUMNAS)} del contrato en todas las filas"


def chequear_unicidad(filas):
    """Verifica que no existan duplicados para la clave (provincia, destino, anio).

    Devuelve (resultado, mensaje), igual que los demás checks.
    """
    # TODO 9 --------------------------------------------------------------
    claves = [(fila["provincia"], fila["destino"], fila["anio"]) for fila in filas]
    duplicados = len(claves) - len(set(claves))
    ok = duplicados == 0
    return ok, f"unicidad: {duplicados} claves duplicadas"
    # ---------------------------------------------------------------------


def chequear_rangos(filas):
    """Verifica que los porcentajes calculados se encuentren en el rango [0, 100].

    Devuelve (resultado, mensaje), igual que los demás checks. Los valores
    None se consideran válidos.
    """
    # TODO 10 -------------------------------------------------------------
    # Se filtran observaciones donde la participación esté fuera del intervalo [0, 100]
    fuera_de_rango = [
        fila
        for fila in filas
        if fila.get("participacion_pct") is not None
        and not (0.0 <= fila["participacion_pct"] <= 100.0)
    ]

    ok = len(fuera_de_rango) == 0
    return ok, f"rangos: {len(fuera_de_rango)} participaciones fuera de [0, 100]"
    # ---------------------------------------------------------------------


def chequear_cobertura(filas):
    """Evalúa la cobertura de las columnas derivadas y prepara una advertencia.

    La ausencia de variación en el primer año es esperable; la falta de rubro
    determina si el check queda como OK o AVISO. Devuelve resultado y mensaje.
    """
    sin_variacion = sum(1 for f in filas if f["var_interanual_pct"] is None)
    sin_rubro = sum(1 for f in filas if f["rubro_principal"] is None)
    ok = sin_rubro == 0
    return ok, (f"cobertura: {sin_variacion} filas sin variación interanual "
                f"(esperable en el primer año), {sin_rubro} sin rubro")


def validar(filas):
    """Ejecuta los controles de calidad y devuelve su detalle.

    Los CRÍTICOS cortan el pipeline lanzando una excepción ("fallar
    temprano y ruidosamente"). La cobertura solo deja una advertencia.

    Returns:
        Lista de diccionarios con el nombre de cada check y su estado.

    Raises:
        ValueError: si falla cualquiera de los controles críticos.
    """
    criticos = [
        chequear_cantidad(filas),
        chequear_columnas(filas),
        chequear_unicidad(filas),
        chequear_rangos(filas),
    ]

    detalle = []
    for ok, mensaje in criticos:
        detalle.append({"check": mensaje, "estado": "OK" if ok else "FALLO"})
        if ok:
            logging.info("  check OK    | %s", mensaje)
        else:
            logging.error("  check FALLO | %s", mensaje)
            raise ValueError(f"Quality check crítico falló -> {mensaje}")

    ok, mensaje = chequear_cobertura(filas)
    detalle.append({"check": mensaje, "estado": "OK" if ok else "AVISO"})
    if ok:
        logging.info("  check OK    | %s", mensaje)
    else:
        logging.warning("  check AVISO | %s", mensaje)

    return detalle


# ======================================================================
# PERSISTENCIA
# ======================================================================
def guardar_csv(filas, carpeta=None, nombre=None):
    """Guarda las filas como CSV y devuelve la ruta del archivo generado.

    El archivo se sobrescribe en cada corrida. Si no se especifican,
    ``carpeta`` y ``nombre`` se toman de la configuración.
    """
    carpeta = carpeta or config.DIR_PROCESSED
    nombre = nombre or config.ARCHIVO_SALIDA_CSV
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, nombre)

    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)

    logging.info("  CSV: %s (%s filas)", ruta, len(filas))
    return ruta


def construir_resumen(filas, detalle_checks):
    """Resume metadatos, estadísticas de exportación y resultados de calidad.

    Args:
        filas: registros transformados del dataset.
        detalle_checks: resultados devueltos por :func:`validar`.

    Returns:
        Diccionario serializable con información del dataset y la corrida.
    """
    # Extracción de valores numéricos válidos
    valores = [
        f["valor_musd"] for f in filas if f.get("valor_musd") is not None
    ]

    # Conjuntos únicos ordenados
    provincias_unicas = sorted({f["provincia"] for f in filas})
    anios_unicos = sorted({f["anio"] for f in filas})
    destinos_unicos = sorted({f["destino"] for f in filas})
    generado = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Métricas agregadas
    total_exportado = round(sum(valores), 2) if valores else 0.0
    promedio_exportado = (
        round(sum(valores) / len(valores), 2) if valores else 0.0
    )
    min_exportado = min(valores) if valores else 0.0
    max_exportado = max(valores) if valores else 0.0

    resumen = {
        "dataset": "Exportaciones por provincia y país de destino — NEA",
        "fuente": "INDEC, API de Series de Tiempo de datos.gob.ar",
        "unidad": "millones de dólares FOB",
        "generado": generado,
        "filas": len(filas),
        "columnas": len(COLUMNAS),
        "periodo": {
            "desde": min(anios_unicos) if anios_unicos else None,
            "hasta": max(anios_unicos) if anios_unicos else None,
        },
        "valor_musd": {
            "minimo": min_exportado if valores else None,
            "maximo": max_exportado if valores else None,
            "promedio": promedio_exportado if valores else None,
        },
        "quality_checks": detalle_checks,
        "fecha_procesamiento": generado,
        "total_filas": len(filas),
        "cant_provincias": len(provincias_unicas),
        "provincias": provincias_unicas,
        "anio_min": min(anios_unicos) if anios_unicos else None,
        "anio_max": max(anios_unicos) if anios_unicos else None,
        "cant_destinos": len(destinos_unicos),
        "total_exportado_musd": total_exportado,
        "promedio_exportado_musd": promedio_exportado,
        "min_exportado_musd": min_exportado,
        "max_exportado_musd": max_exportado,
    }

    return resumen

def guardar_resumen(resumen, carpeta=None, nombre=None):
    """Escribe el resumen como JSON legible y devuelve la ruta del archivo.

    Si no se especifican, ``carpeta`` y ``nombre`` se toman de la configuración.
    """
    carpeta = carpeta or config.DIR_PROCESSED
    nombre = nombre or config.ARCHIVO_SALIDA_JSON
    os.makedirs(carpeta, exist_ok=True)
    ruta_archivo = os.path.join(carpeta, nombre)

    with open(ruta_archivo, mode="w", encoding="utf-8") as f:
        json.dump(resumen, f, indent=4, ensure_ascii=False)
    logging.info("  JSON: %s", ruta_archivo)
    return ruta_archivo


def escribir_log_corrida(resumen, carpeta=None, nombre=None):
    """Añade al log una línea con fecha, estado, cantidad de filas y período.

    Devuelve la ruta del archivo de log; si no se indica, usa la configuración.
    """
    carpeta = carpeta or config.DIR_LOGS
    nombre = nombre or config.ARCHIVO_LOG
    os.makedirs(carpeta, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    periodo = resumen["periodo"]
    linea_log = (
        f"[{timestamp}] OK | {resumen['filas']} filas | "
        f"{periodo['desde']}-{periodo['hasta']}\n"
    )
    ruta_log = os.path.join(carpeta, nombre)

    with open(ruta_log, mode="a", encoding="utf-8") as f:
        f.write(linea_log)
    logging.info("  log: %s", ruta_log)
    return ruta_log
    # ---------------------------------------------------------------------


def cargar(filas):
    """Valida las filas y guarda CSV, resumen JSON y log de la corrida.

    Returns:
        El resumen de la corrida, incluido el detalle de los controles.

    Raises:
        ValueError: si falla un control de calidad crítico.
    """
    logging.info("LOAD: validando")
    detalle = validar(filas)

    logging.info("LOAD: guardando")
    guardar_csv(filas)
    resumen = construir_resumen(filas, detalle)
    guardar_resumen(resumen)
    escribir_log_corrida(resumen)

    logging.info("LOAD OK")
    return resumen
