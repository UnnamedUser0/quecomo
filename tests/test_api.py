"""Pruebas unitarias y de integración para la API REST de la App ¿Qué Como?."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from quecomo.configuracion import Aplicacion
from quecomo.presentacion.api import crear_api_router


@pytest.fixture
def client_api(app_demo: Aplicacion) -> TestClient:
    app = FastAPI()
    app.include_router(crear_api_router(app_demo))
    return TestClient(app)


def test_health(client_api: TestClient):
    response = client_api.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["app"] == "¿Qué Como?"


def test_listar_restaurantes(client_api: TestClient):
    response = client_api.get("/api/v1/restaurantes")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 8
    nombres = [r["nombre"] for r in data]
    assert "Mariscos El Faro Azul" in nombres


def test_detalle_restaurante_existente(client_api: TestClient):
    response = client_api.get("/api/v1/restaurantes/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["nombre"] == "Mariscos El Faro Azul"
    assert "menus" in data
    assert "promociones" in data
    assert len(data["menus"]) > 0


def test_detalle_restaurante_inexistente(client_api: TestClient):
    response = client_api.get("/api/v1/restaurantes/9999")
    assert response.status_code == 404


def test_buscar_restaurantes(client_api: TestClient):
    response = client_api.get("/api/v1/buscar?texto=tacos")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert any("Tacos" in r["nombre"] for r in data)


def test_flujo_completo_transaccion_y_evaluacion(client_api: TestClient):
    # 1. Cliente registra consumo (Ana López id=1 en Faro Azul id=1)
    res_reg = client_api.post(
        "/api/v1/transacciones",
        json={"usuario_id": 1, "restaurante_id": 1, "importe": 320.0},
    )
    assert res_reg.status_code == 200
    datos_t = res_reg.json()
    tid = datos_t["transaccion_id"]
    assert datos_t["estado"] == "PENDIENTE"

    # 2. Intentar evaluar antes de completarse (debe fallar por RN-01)
    res_eval_invalida = client_api.post(
        "/api/v1/evaluaciones",
        json={
            "usuario_id": 1,
            "transaccion_id": tid,
            "calificacion": 5,
            "comentario": "Comida deliciosa y fresco todo.",
        },
    )
    assert res_eval_invalida.status_code == 400

    # 3. Locatario dueño (Héctor Salas id=4) confirma
    res_conf = client_api.post(
        f"/api/v1/transacciones/{tid}/confirmar",
        json={"usuario_id": 4},
    )
    assert res_conf.status_code == 200

    # 4. Locatario dueño completa
    res_comp = client_api.post(
        f"/api/v1/transacciones/{tid}/completar",
        json={"usuario_id": 4},
    )
    assert res_comp.status_code == 200
    assert res_comp.json()["puede_evaluarse"] is True

    # 5. Cliente evalúa exitosamente
    res_eval = client_api.post(
        "/api/v1/evaluaciones",
        json={
            "usuario_id": 1,
            "transaccion_id": tid,
            "calificacion": 5,
            "comentario": "Excelente comida y atención de primera.",
        },
    )
    assert res_eval.status_code == 200
    assert "publicada" in res_eval.json()["mensaje"].lower()

    # 6. Re-evaluar la misma transacción debe ser rechazado (RN-06)
    res_reeval = client_api.post(
        "/api/v1/evaluaciones",
        json={
            "usuario_id": 1,
            "transaccion_id": tid,
            "calificacion": 4,
            "comentario": "Intentando evaluar dos veces el mismo consumo.",
        },
    )
    assert res_reeval.status_code == 400
