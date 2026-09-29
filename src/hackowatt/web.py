"""Local web delivery for the native HackoWatt presentation."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .issue_date_forecast import ForecastRequest, ForecastResult, forecast_from_issue_date
from .presentation import (render_historical_dashboard, render_issue_date_forecast,
                           render_renewable_dashboard)
from .services import DashboardService


class IssueDateRequest(BaseModel):
    """Browser contract for the supported selected-model forecast."""

    forecast_start_local: str
    horizon_hours: Literal[24, 72, 168] = 24
    forecast_weather: str | None = None


def create_web_app(generated_directory: Path) -> FastAPI:
    """Create a local app that hosts visual assets and calls public use cases."""
    service = DashboardService(generated_directory)
    latest_result: ForecastResult | None = None
    app = FastAPI(title="HackoWatt Family", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return SHELL

    @app.get("/views/historical", response_class=HTMLResponse)
    def historical() -> str:
        return render_historical_dashboard(service.historical_dashboard_source())

    @app.get("/views/forecast", response_class=HTMLResponse)
    def forecast() -> str:
        if latest_result is None:
            return unavailable_view("Issue-date forecast", "Choose an issue date and horizon in the header, then run the selected model.")
        return render_issue_date_forecast(latest_result)

    @app.get("/views/planning", response_class=HTMLResponse)
    def planning() -> str:
        return render_renewable_dashboard(service.renewable_dashboard_source())

    @app.post("/api/issue-date-forecast")
    def issue_date_forecast(request: IssueDateRequest) -> dict:
        nonlocal latest_result
        weather_path = Path(request.forecast_weather) if request.forecast_weather else None
        try:
            latest_result = forecast_from_issue_date(ForecastRequest(
                hourly_path=service.historical().directory / "hourly.csv",
                forecast_start_local=request.forecast_start_local,
                horizon_hours=request.horizon_hours,
                forecast_weather_path=weather_path,
            ))
        except (FileNotFoundError, ValueError, RuntimeError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"status": "completed", "model": latest_result.model_id,
                "horizon_hours": latest_result.manifest["horizon_hours"]}

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "generated_directory": str(generated_directory)}

    return app


def unavailable_view(title: str, detail: str) -> str:
    return f"""<!doctype html><title>{title}</title><style>
body{{font:16px system-ui;margin:3rem;color:#253e5b;background:#f3f6f8}}
main{{max-width:48rem;padding:2rem;background:white;border-radius:1rem}}
</style><main><h1>{title}</h1><p>{detail}</p></main>"""


SHELL = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HackoWatt Family</title><style>
:root{font-family:Inter,Segoe UI,Arial,sans-serif;color:#213d50;background:#eef3f0}*{box-sizing:border-box}body{margin:0}.appbar{min-height:74px;display:flex;align-items:center;gap:20px;padding:10px 28px;background:#153e42;color:white;box-shadow:0 2px 10px #102c3030}.brand{font-size:20px;font-weight:750;letter-spacing:.2px}.brand small{display:block;font-size:10px;letter-spacing:1.3px;color:#c6e4d9}.nav{display:flex;gap:5px;flex:1}.nav button,.run,input,select{border:0;border-radius:9px;padding:10px 12px;font:inherit}.nav button{background:transparent;color:#d8ece5;font-weight:650;cursor:pointer}.nav button:hover,.nav button[aria-selected=true]{background:#2d5b5e;color:white}.controls{display:flex;gap:7px;align-items:center}.controls label{font-size:11px;color:#d8ece5;display:grid;gap:2px}.controls input,.controls select{color:#213d50;padding:7px}.run{background:#e7b663;color:#273b36;font-weight:700;cursor:pointer}.run:disabled{opacity:.65;cursor:wait}.notice{font-size:12px;color:#d8ece5}@media(max-width:1050px){.appbar{flex-wrap:wrap;padding:12px 16px}.nav{order:3;flex-basis:100%;overflow:auto}.controls{margin-left:auto}}iframe{display:block;width:100%;height:calc(100vh - 74px);border:0;background:#f3f6f8}.view[hidden]{display:none}</style></head><body><header class="appbar"><div class="brand">☀ HackoWatt<small>HOME ENERGY</small></div><nav class="nav" aria-label="Application sections"><button aria-selected="true" data-view="historical">Historical profile</button><button aria-selected="false" data-view="forecast">Issue-date forecast</button><button aria-selected="false" data-view="planning">Energy planning</button></nav><div class="controls"><label>Forecast start<input id="start" type="datetime-local" value="2025-09-10T00:00"></label><label>Horizon<select id="horizon"><option value="24">24 hours</option><option value="72">72 hours</option><option value="168">168 hours</option></select></label><button class="run" id="runForecast">Run forecast</button></div><span class="notice" id="notice" role="status"></span></header><main><iframe class="view" id="historical" title="Historical household profile" src="/views/historical"></iframe><iframe class="view" id="forecast" title="Issue-date forecast" src="/views/forecast" hidden></iframe><iframe class="view" id="planning" title="Energy planning" src="/views/planning" hidden></iframe></main><script>
const views=[...document.querySelectorAll('.view')],buttons=[...document.querySelectorAll('[data-view]')],notice=document.querySelector('#notice'),run=document.querySelector('#runForecast');buttons.forEach(button=>button.onclick=()=>{views.forEach(view=>view.hidden=view.id!==button.dataset.view);buttons.forEach(item=>item.setAttribute('aria-selected',item===button));});run.onclick=async()=>{run.disabled=true;notice.textContent='Training selected model…';try{const response=await fetch('/api/issue-date-forecast',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({forecast_start_local:document.querySelector('#start').value,horizon_hours:+document.querySelector('#horizon').value})});const body=await response.json();if(!response.ok)throw new Error(body.detail||'Forecast failed');notice.textContent=`${body.model.replaceAll('_',' ')} complete`;document.querySelector('#forecast').src='/views/forecast?refresh='+Date.now();buttons.find(x=>x.dataset.view==='forecast').click();}catch(error){notice.textContent=error.message;}finally{run.disabled=false;}};
</script></body></html>"""
