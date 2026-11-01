"""
Paralelizacion de las corridas masivas.

Replica `plan(multisession, workers = parallel::detectCores() - 1)` de
Calculo_Reserva_Matematica.R: usa todos los nucleos del equipo menos 1
(para no saturar la maquina mientras se corre el calculo), con un minimo
de 1.

Usa procesos (concurrent.futures.ProcessPoolExecutor), no hilos: cada
cedula es independiente de las demas y el calculo es intensivo en CPU
(1439 meses de proyeccion por cedula), asi que procesos aprovechan
multiples nucleos de verdad (a diferencia de hilos, limitados por el GIL
de Python en la parte del bucle de mortalidad que no es numpy vectorizado).

Si por algun motivo el pool de procesos falla (algunos entornos
corporativos con restricciones raras de Windows pueden bloquear la
creacion de subprocesos), se hace un fallback automatico a ejecucion
secuencial en el mismo proceso, para que la corrida masiva nunca falle
del todo por esto -- solo corre mas lento.
"""

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable, List, Optional, TypeVar

T = TypeVar("T")


def numero_workers(n_tareas: int) -> int:
    """Nucleos del equipo menos 1 (minimo 1), sin pasarse del numero de
    tareas a procesar (no tiene sentido pedir mas workers que filas)."""
    cpus = os.cpu_count() or 1
    workers = max(cpus - 1, 1)
    if n_tareas > 0:
        workers = min(workers, n_tareas)
    return workers


def ejecutar_en_paralelo(
    funcion: Callable[..., T],
    argumentos: List[tuple],
    callback_progreso: Optional[Callable[[int, int], None]] = None,
) -> List[T]:
    """
    Ejecuta funcion(*args) para cada tupla de argumentos en argumentos,
    usando un pool de procesos (nucleos del equipo - 1). Devuelve los
    resultados EN EL MISMO ORDEN que argumentos (no en el orden en que
    van terminando).

    Si la creacion del pool de procesos falla por cualquier motivo, hace
    fallback a ejecucion secuencial en el proceso actual (mismo orden,
    mismo callback de progreso), para que la corrida nunca se caiga del
    todo por un problema de paralelizacion.
    """
    total = len(argumentos)
    if total == 0:
        return []

    workers = numero_workers(total)

    if workers <= 1:
        return _ejecutar_secuencial(funcion, argumentos, callback_progreso)

    try:
        resultados: List[Optional[T]] = [None] * total
        completadas = 0
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futuros = {executor.submit(funcion, *args): i for i, args in enumerate(argumentos)}
            for futuro in as_completed(futuros):
                indice = futuros[futuro]
                resultados[indice] = futuro.result()
                completadas += 1
                if callback_progreso is not None:
                    callback_progreso(completadas, total)
        return resultados  # type: ignore[return-value]
    except Exception:  # noqa: BLE001
        # Fallback: si el pool de procesos no se pudo crear o fallo de forma
        # no recuperable (por ejemplo restricciones del entorno), se sigue
        # con ejecucion secuencial en vez de dejar caer toda la corrida.
        return _ejecutar_secuencial(funcion, argumentos, callback_progreso)


def _ejecutar_secuencial(
    funcion: Callable[..., T],
    argumentos: List[tuple],
    callback_progreso: Optional[Callable[[int, int], None]],
) -> List[T]:
    total = len(argumentos)
    resultados = []
    for i, args in enumerate(argumentos):
        resultados.append(funcion(*args))
        if callback_progreso is not None:
            callback_progreso(i + 1, total)
    return resultados
