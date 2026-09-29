"""Local web delivery for the native HackoWatt presentation.

The browser talks to this thin adapter, never directly to simulation or model
modules.  It deliberately keeps a small HTTP API so future controls can invoke
Python use cases without replacing the UI again.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .presentation import (render_forecast_dashboard, render_historical_dashboard,
                           render_renewable_dashboard)
from .services import DashboardService, run_forecast


class ForecastRequest(BaseModel):
    """Safe, intentionally small contract for a user-triggered model run."""

    test_days: int = Field(default=90, ge=14, le=365)
    origin_stride_hours: int = Field(default=168, ge=24, le=24 * 28)


def create_web_app(generated_directory: Path, forecast_directory: Path) -> FastAPI:
    """Create the local UI server bound to one generated scenario."""
    service = DashboardService(generated_directory, forecast_directory)
    app = FastAPI(title="HackoWatt Family", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return SHELL

    @app.get("/views/historical", response_class=HTMLResponse)
    def historical() -> str:
        return render_historical_dashboard(service.historical_dashboard_source())

    @app.get("/views/forecast", response_class=HTMLResponse)
    def forecast() -> str:
        try:
            artifacts = service.forecast()
        except FileNotFoundError as error:
            return unavailable_view("Forecast unavailable", str(error))
        return render_forecast_dashboard(artifacts.predictions, artifacts.metrics)

    @app.get("/views/planning", response_class=HTMLResponse)
    def planning() -> str:
        return render_renewable_dashboard(service.renewable_dashboard_source())

    @app.post("/api/forecast")
    def trigger_forecast(request: ForecastRequest) -> dict:
        """Run the canonical forecast experiment for the currently loaded home."""
        hourly_path = service.historical().directory / "hourly.csv"
        try:
            artifacts = run_forecast(hourly_path, forecast_directory, request.test_days,
                                     request.origin_stride_hours)
        except (FileNotFoundError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {
            "status": "completed",
            "origins": artifacts.specification.get("origins"),
            "models": sorted(artifacts.predictions.model_id.unique().tolist()),
        }

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "generated_directory": str(generated_directory)}

    return app


def unavailable_view(title: str, detail: str) -> str:
    return f"""<!doctype html><title>{title}</title><style>
body{{font:16px system-ui;margin:3rem;color:#253e5b;background:#f3f6f8}}
main{{max-width:48rem;padding:2rem;background:white;border-radius:1rem}}
</style><main><h1>{title}</h1><p>{detail}</p>
<p>Use the <strong>Run forecast</strong> button in the application header to create it.</p></main>"""


SHELL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HackoWatt Family</title><style>
:root{font-family:Inter,Segoe UI,Arial,sans-serif;color:#213d50;background:#eef3f0}
*{box-sizing:border-box}body{margin:0}.appbar{height:72px;display:flex;align-items:center;gap:28px;padding:0 32px;background:#153e42;color:white;box-shadow:0 2px 10px #102c3030}.brand{font-size:20px;font-weight:750;letter-spacing:.2px}.brand small{display:block;font-size:10px;letter-spacing:1.3px;color:#c6e4d9}.nav{display:flex;gap:5px;flex:1}.nav button,.run{border:0;border-radius:9px;padding:10px 14px;font:inherit;font-weight:650;cursor:pointer}.nav button{background:transparent;color:#d8ece5}.nav button:hover,.nav button[aria-selected=true]{background:#2d5b5e;color:white}.run{background:#e7b663;color:#273b36}.run:disabled{opacity:.65;cursor:wait}.notice{margin-left:auto;font-size:13px;color:#d8ece5}@media(max-width:760px){.appbar{height:auto;flex-wrap:wrap;padding:14px 16px;gap:10px}.nav{order:3;flex-basis:100%;overflow:auto}.notice{display:none}}
iframe{display:block;width:100%;height:calc(100vh - 72px);border:0;background:#f3f6f8}.view[hidden]{display:none}
</style></head><body><header class="appbar"><div class="brand">☀ HackoWatt<small>HOME ENERGY</small></div><nav class="nav" aria-label="Application sections"><button aria-selected="true" data-view="historical">Historical profile</button><button aria-selected="false" data-view="forecast">Forecast quality</button><button aria-selected="false" data-view="planning">Energy planning</button></nav><span class="notice" id="notice" role="status"></span><button class="run" id="runForecast">Run forecast</button></header><main><iframe class="view" id="historical" title="Historical household profile" src="/views/historical"></iframe><iframe class="view" id="forecast" title="Forecast quality" src="/views/forecast" hidden></iframe><iframe class="view" id="planning" title="Energy planning" src="/views/planning" hidden></iframe></main><script>
const views=[...document.querySelectorAll('.view')],buttons=[...document.querySelectorAll('[data-view]')],notice=document.querySelector('#notice'),run=document.querySelector('#runForecast');
buttons.forEach(button=>button.onclick=()=>{views.forEach(view=>view.hidden=view.id!==button.dataset.view);buttons.forEach(item=>item.setAttribute('aria-selected',item===button));});
run.onclick=async()=>{run.disabled=true;notice.textContent='Running the forecast…';try{const response=await fetch('/api/forecast',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const body=await response.json();if(!response.ok)throw new Error(body.detail||'Forecast failed');notice.textContent=`Forecast complete · ${body.origins} origins`;document.querySelector('#forecast').src='/views/forecast?refresh='+Date.now();document.querySelector('#planning').src='/views/planning?refresh='+Date.now();}catch(error){notice.textContent=error.message;}finally{run.disabled=false;}};
</script></body></html>"""
