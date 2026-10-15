"""API REST para clientes móviles y externos de la App ¿Qué Como?.

Capa de PRESENTACIÓN: expone los servicios de aplicación a través de endpoints HTTP REST
con esquemas validados y documentación interactiva OpenAPI (/docs).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..aplicacion.servicio_busqueda import CriteriosBusqueda, Orden
from ..configuracion import Aplicacion
from ..dominio.entidades import LONGITUD_MAXIMA_COMENTARIO, LONGITUD_MINIMA_COMENTARIO
from ..dominio.estados import EstadoRestaurante
from ..dominio.excepciones import EvaluacionNoPermitida, TransicionInvalida


class RegistroTransaccionReq(BaseModel):
    usuario_id: int = Field(..., description="ID del cliente que realiza el consumo")
    restaurante_id: int = Field(..., description="ID del restaurante")
    importe: float = Field(..., gt=0, description="Monto consumido en pesos (MXN)")


class RegistroEvaluacionReq(BaseModel):
    usuario_id: int = Field(..., description="ID del autor de la evaluación")
    transaccion_id: int = Field(..., description="ID del consumo completado que respalda la evaluación")
    calificacion: int = Field(..., ge=1, le=5, description="Calificación entera de 1 a 5 estrellas")
    comentario: str = Field(
        ...,
        min_length=LONGITUD_MINIMA_COMENTARIO,
        max_length=LONGITUD_MAXIMA_COMENTARIO,
        description="Opinión detallada sobre comida, servicio y lugar",
    )


class AccionTransaccionReq(BaseModel):
    usuario_id: int = Field(..., description="ID del locatario dueño o cliente")


def crear_api_router(app: Aplicacion) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["App ¿Qué Como? - REST API"])

    @router.get("/health", summary="Estado de salud de la App")
    def health() -> dict[str, Any]:
        return {
            "status": "online",
            "app": "¿Qué Como?",
            "version": "1.0.0",
            "tipo": "Mobile / Web App & REST API",
        }

    @router.get("/restaurantes", summary="Listar restaurantes activos")
    def listar_restaurantes() -> list[dict[str, Any]]:
        activos = [r for r in app.restaurantes.listar() if r.estado == EstadoRestaurante.ACTIVO]
        resultado = []
        for r in activos:
            ranking = app.ranking.calcular(r.id)
            resultado.append(
                {
                    "id": r.id,
                    "nombre": r.nombre,
                    "categoria": r.categoria,
                    "precio_promedio": float(r.precio_promedio),
                    "zona": r.ubicacion.zona,
                    "direccion": r.ubicacion.direccion,
                    "formas_pago": list(r.formas_pago),
                    "calificacion": ranking.promedio,
                    "total_evaluaciones": ranking.total,
                }
            )
        return resultado

    @router.get("/restaurantes/{restaurante_id}", summary="Detalle de un restaurante")
    def detalle_restaurante(restaurante_id: int) -> dict[str, Any]:
        r = app.restaurantes.obtener(restaurante_id)
        if not r or r.estado != EstadoRestaurante.ACTIVO:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurante no encontrado")

        ranking = app.ranking.calcular(r.id)
        evaluaciones = app.evaluaciones.obtener_por_restaurante(r.id)
        evaluaciones_dto = []
        for e in sorted(evaluaciones, key=lambda x: x.fecha, reverse=True):
            autor = app.usuarios.obtener(e.usuario_id)
            evaluaciones_dto.append(
                {
                    "id": e.id,
                    "autor": autor.nombre_publico() if autor else "Usuario",
                    "calificacion": e.calificacion,
                    "comentario": e.comentario,
                    "fecha": e.fecha.isoformat(),
                    "transaccion_respaldo_id": e.transaccion_id,
                }
            )

        menus_dto = []
        for m in r.menus:
            menus_dto.append(
                {
                    "nombre": m.nombre,
                    "productos": [
                        {"nombre": p.nombre, "precio": float(p.precio), "descripcion": p.descripcion}
                        for p in m.productos
                    ],
                }
            )

        return {
            "id": r.id,
            "nombre": r.nombre,
            "descripcion": r.descripcion,
            "categoria": r.categoria,
            "ubicacion": {
                "direccion": r.ubicacion.direccion,
                "latitud": r.ubicacion.latitud,
                "longitud": r.ubicacion.longitud,
                "zona": r.ubicacion.zona,
            },
            "precio_promedio": float(r.precio_promedio),
            "formas_pago": list(r.formas_pago),
            "calificacion": ranking.promedio,
            "total_evaluaciones": ranking.total,
            "distribucion_calificaciones": ranking.distribucion,
            "menus": menus_dto,
            "promociones": [
                {
                    "descripcion": p.descripcion,
                    "inicio": p.inicio.isoformat(),
                    "fin": p.fin.isoformat(),
                    "condiciones": p.condiciones,
                }
                for p in r.promociones
            ],
        }

    @router.get("/buscar", summary="Buscar y filtrar restaurantes")
    def buscar(
        texto: str = Query("", description="Texto libre o platillo"),
        categoria: str = Query("Todas", description="Tipo de comida"),
        precio_maximo: float = Query(600, ge=0, description="Precio máximo en MXN"),
        punto: str = Query("Centro", description="Punto de referencia"),
        distancia_maxima: float = Query(15, ge=0, description="Distancia máxima en km"),
        forma_pago: str = Query("Todas", description="Forma de pago en el local"),
        calificacion_minima: float = Query(0, ge=0, le=5, description="Calificación mínima"),
        solo_promocion: bool = Query(False, description="Solo con promoción vigente"),
        orden: str = Query(Orden.RANKING.value, description="Criterio de ordenamiento"),
    ) -> list[dict[str, Any]]:
        criterios = CriteriosBusqueda(
            texto=texto,
            categoria=None if categoria == "Todas" else categoria,
            precio_maximo=precio_maximo,
            punto=app.punto(punto),
            distancia_maxima_km=distancia_maxima,
            forma_pago=None if forma_pago == "Todas" else forma_pago,
            calificacion_minima=calificacion_minima if calificacion_minima > 0 else None,
            solo_con_promocion=solo_promocion,
            orden=Orden(orden) if orden in [o.value for o in Orden] else Orden.RANKING,
        )
        resultados = app.busqueda.buscar(criterios)
        return [
            {
                "id": res.restaurante.id,
                "nombre": res.restaurante.nombre,
                "categoria": res.restaurante.categoria,
                "precio_promedio": float(res.restaurante.precio_promedio),
                "distancia_km": res.distancia_km,
                "calificacion": res.ranking.promedio,
                "total_evaluaciones": res.ranking.total,
                "abierto": res.abierto,
            }
            for res in resultados
        ]

    @router.post("/transacciones", summary="Registrar consumo (HU-06)")
    def registrar_consumo(req: RegistroTransaccionReq) -> dict[str, Any]:
        try:
            t = app.servicio_transacciones.registrar(
                usuario_id=req.usuario_id,
                restaurante_id=req.restaurante_id,
                importe=req.importe,
            )
            return {
                "mensaje": f"Consumo #{t.id} registrado correctamente.",
                "transaccion_id": t.id,
                "estado": t.estado.value,
                "puede_evaluarse": t.puede_evaluarse(),
            }
        except ValueError as err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err

    @router.post("/transacciones/{transaccion_id}/confirmar", summary="Confirmar consumo (Locatario)")
    def confirmar_consumo(transaccion_id: int, req: AccionTransaccionReq) -> dict[str, Any]:
        try:
            app.servicio_transacciones.confirmar(req.usuario_id, transaccion_id)
            t = app.transacciones.obtener(transaccion_id)
            return {"mensaje": "Consumo confirmado.", "estado": t.estado.value if t else "CONFIRMADA"}
        except (ValueError, TransicionInvalida) as err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err

    @router.post("/transacciones/{transaccion_id}/completar", summary="Completar consumo (Locatario)")
    def completar_consumo(transaccion_id: int, req: AccionTransaccionReq) -> dict[str, Any]:
        try:
            app.servicio_transacciones.completar(req.usuario_id, transaccion_id)
            t = app.transacciones.obtener(transaccion_id)
            return {
                "mensaje": "Consumo completado. Ahora el cliente puede evaluarlo.",
                "estado": t.estado.value if t else "COMPLETADA",
                "puede_evaluarse": t.puede_evaluarse() if t else True,
            }
        except (ValueError, TransicionInvalida) as err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err

    @router.post("/evaluaciones", summary="Publicar evaluación respaldada (CU-01 / RN-01)")
    def publicar_evaluacion(req: RegistroEvaluacionReq) -> dict[str, Any]:
        try:
            e = app.controlador_evaluacion.registrar_evaluacion(
                usuario_id=req.usuario_id,
                transaccion_id=req.transaccion_id,
                calificacion=req.calificacion,
                comentario=req.comentario,
            )
            ranking = app.ranking.calcular(e.restaurante_id)
            return {
                "mensaje": "Evaluación publicada y vinculada con éxito al consumo.",
                "evaluacion_id": e.id,
                "calificacion": e.calificacion,
                "nuevo_promedio_restaurante": ranking.promedio,
            }
        except (EvaluacionNoPermitida, ValueError) as err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err

    return router
