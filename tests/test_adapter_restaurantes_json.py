"""Pruebas unitarias para el adaptador JSON de restaurantes."""

import json
from decimal import Decimal

import pytest

from quecomo.dominio.estados import EstadoRestaurante
from quecomo.infraestructura.adapter_restaurantes_json import (
    AdapterRestaurantesJSON,
    ErrorFormatoRestaurantes,
)


@pytest.fixture
def registro_valido():
    return {
        "id": 1,
        "nombre": "Tacos El Pastor",
        "descripcion": "Los mejores tacos al pastor",
        "categoria": "Mexicana",
        "ubicacion": {
            "direccion": "Av. Rosales 123",
            "latitud": 29.0892,
            "longitud": -110.9613,
            "zona": "Centro",
        },
        "horario": {
            "dias": [0, 1, 2, 3, 4, 5, 6],
            "apertura": "08:00:00",
            "cierre": "22:00:00",
        },
        "formas_pago": ["Efectivo", "Tarjeta de débito"],
        "precio_promedio": "120.50",
        "fecha_apertura": "2020-01-15",
        "locatario_id": 4,
        "estado": "ACTIVO",
    }


def test_convertir_registro_valido(registro_valido):
    restaurante = AdapterRestaurantesJSON.convertir(registro_valido)
    assert restaurante.id == 1
    assert restaurante.nombre == "Tacos El Pastor"
    assert restaurante.categoria == "Mexicana"
    assert restaurante.ubicacion.zona == "Centro"
    assert restaurante.precio_promedio == Decimal("120.50")
    assert restaurante.estado == EstadoRestaurante.ACTIVO


def test_convertir_registro_invalido():
    with pytest.raises(ErrorFormatoRestaurantes, match="Registro de restaurante inválido"):
        AdapterRestaurantesJSON.convertir({"id": "no-numero"})


def test_cargar_archivo_valido(tmp_path, registro_valido):
    archivo_json = tmp_path / "restaurantes.json"
    archivo_json.write_text(json.dumps([registro_valido]), encoding="utf-8")

    adapter = AdapterRestaurantesJSON(archivo_json)
    restaurantes = adapter.cargar()

    assert len(restaurantes) == 1
    assert restaurantes[0].nombre == "Tacos El Pastor"


def test_cargar_archivo_inexistente(tmp_path):
    adapter = AdapterRestaurantesJSON(tmp_path / "no_existe.json")
    with pytest.raises(ErrorFormatoRestaurantes, match="No se pudo leer el archivo JSON"):
        adapter.cargar()


def test_cargar_archivo_no_lista(tmp_path):
    archivo_json = tmp_path / "invalido.json"
    archivo_json.write_text(json.dumps({"error": "no es lista"}), encoding="utf-8")

    adapter = AdapterRestaurantesJSON(archivo_json)
    with pytest.raises(ErrorFormatoRestaurantes, match="El archivo debe contener una lista JSON"):
        adapter.cargar()
