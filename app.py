"""Punto de entrada de la aplicación ¿Qué Como? (App Móvil/Web & REST API).

Uso local:
    python app.py                      → http://127.0.0.1:7860

En la nube (Render, Railway, etc.) la plataforma define la variable PORT;
en ese caso la app escucha en 0.0.0.0:$PORT automáticamente.

Rutas y funcionalidades:
    /              → App móvil/web interactiva (Gradio con soporte PWA instalable)
    /docs          → Documentación interactiva de la API REST (Swagger UI)
    /redoc         → Documentación alternativa de la API REST (ReDoc)
    /api/v1/...    → Endpoints REST para clientes móviles / aplicaciones externas
    /manifest.json → Manifiesto PWA para instalación como App nativa en móviles/desktop
"""

import os
import sys
from pathlib import Path

# Permite ejecutar `python app.py` sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import gradio as gr
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from quecomo.configuracion import crear_aplicacion
from quecomo.presentacion.api import crear_api_router
from quecomo.presentacion.interfaz import CSS, TEMA, construir_interfaz

app_core = crear_aplicacion()

# 1. Aplicación FastAPI con documentación OpenAPI para la App
api_app = FastAPI(
    title="¿Qué Como? — App & API Backend",
    description=(
        "Backend y API REST de la aplicación ¿Qué Como? "
        "Permite descubrir, comparar y evaluar restaurantes con evaluaciones respaldadas por consumos reales."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 2. Archivos estáticos y manifiesto PWA para instalación de la App
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    api_app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @api_app.get("/manifest.json", include_in_schema=False)
    def manifest():
        return FileResponse(static_dir / "manifest.json", media_type="application/manifest+json")

    @api_app.get("/sw.js", include_in_schema=False)
    def service_worker():
        return FileResponse(static_dir / "sw.js", media_type="application/javascript")

# 3. Router de endpoints REST para consumo por apps móviles
api_app.include_router(crear_api_router(app_core))

# 4. Metadatos de la PWA para la cabecera HTML
head_pwa = """
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#12203A">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Qué Como">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
<script>
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js');
    });
  }
</script>
"""

# 5. Montar interfaz interactiva PWA en la raíz
demo = construir_interfaz(app_core)
app = gr.mount_gradio_app(
    api_app,
    demo,
    path="/",
    pwa=True,
    theme=TEMA,
    css=CSS,
    head=head_pwa,
)


def configuracion_servidor() -> tuple[str, int]:
    """Host y puerto: en la nube usa 0.0.0.0:$PORT; en local, 127.0.0.1:7860."""
    puerto_nube = os.getenv("PORT")
    host = os.getenv("GRADIO_SERVER_NAME") or ("0.0.0.0" if puerto_nube else "127.0.0.1")
    puerto = int(os.getenv("GRADIO_SERVER_PORT") or puerto_nube or 7860)
    return host, puerto


if __name__ == "__main__":
    host, puerto = configuracion_servidor()
    print(f"* Iniciando App ¿Qué Como? en http://{host}:{puerto}")
    print(f"* Documentación API Swagger en http://{host}:{puerto}/docs")
    uvicorn.run(app, host=host, port=puerto)
