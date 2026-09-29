"""Renderer for one forecast issued at a user-selected local time."""
from __future__ import annotations

import json

from ..issue_date_forecast import ForecastResult


def render_issue_date_forecast(result: ForecastResult) -> str:
    """Render the selected model's prediction, actual backtest, and manifest."""
    forecast = result.forecast.copy()
    payload = {
        "timestamps": forecast["timestamp_local"].tolist(),
        "forecast": forecast["forecast_kwh"].round(4).tolist(),
        "actual": result.backtest_actual.round(4).tolist(),
        "model": result.model_id.replace("_", " ").title(),
        "horizon": result.manifest["horizon_hours"],
        "metric": result.manifest["metric"],
        "weather": result.manifest["forecast_weather_source"],
    }
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c")
    return HTML.replace("/* DATA */", "const D=" + data + ";")


HTML = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
:root{font-family:Inter,Segoe UI,Arial,sans-serif;color:#213d50;background:#eef3f0}body{margin:0;padding:28px;max-width:1280px}.eyebrow{font-size:12px;font-weight:700;letter-spacing:.12em;color:#39705f}h1{margin:.25rem 0}p{line-height:1.5;color:#54706e}.cards{display:grid;grid-template-columns:repeat(4,minmax(130px,1fr));gap:14px;margin:22px 0}.card,section{background:#fff;border:1px solid #d7e2de;border-radius:14px;padding:18px;box-shadow:0 3px 14px #153e4210}.card span{font-size:12px;color:#5c7771}.card strong{display:block;font-size:22px;margin-top:6px}canvas{width:100%;height:380px;display:block}.legend{display:flex;gap:18px;font-size:13px}.dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:5px}.table{overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:9px;border-bottom:1px solid #e4ece8;text-align:right}th:first-child,td:first-child{text-align:left}@media(max-width:700px){body{padding:16px}.cards{grid-template-columns:repeat(2,1fr)}canvas{height:290px}}</style>
<p class="eyebrow">ISSUE-DATE FORECAST</p><h1 id="title"></h1><p id="subtitle"></p><div class="cards" id="cards"></div><section><h2>Forecast against historical backtest</h2><canvas id="chart" aria-label="Actual and forecast electricity demand"></canvas><div class="legend"><span><i class="dot" style="background:#183e42"></i>Actual load</span><span><i class="dot" style="background:#e08a3c"></i>Selected forecast</span></div></section><section class="table"><h2>Hourly prediction</h2><table><thead><tr><th>Polish local time</th><th>Forecast kWh</th><th>Actual kWh</th></tr></thead><tbody id="rows"></tbody></table></section><script>/* DATA */
const $=id=>document.getElementById(id),max=Math.max(1,...D.actual,...D.forecast);$('title').textContent=`${D.horizon}-hour ${D.model}`;$('subtitle').textContent=`Weather: ${D.weather}. This historical backtest trains only on data known before the selected issue time.`;$('cards').innerHTML=[['Selected model',D.model],['Horizon',D.horizon+' hours'],['MAE',(D.metric.mae??0).toFixed(3)+' kWh'],['WAPE',(D.metric.wape_pct??0).toFixed(1)+'%']].map(([k,v])=>`<div class="card"><span>${k}</span><strong>${v}</strong></div>`).join('');$('rows').innerHTML=D.timestamps.map((t,i)=>`<tr><td>${new Date(t).toLocaleString()}</td><td>${D.forecast[i].toFixed(3)}</td><td>${D.actual[i].toFixed(3)}</td></tr>`).join('');function draw(){let c=$('chart'),r=c.getBoundingClientRect(),d=devicePixelRatio||1;c.width=r.width*d;c.height=r.height*d;let x=c.getContext('2d');x.scale(d,d);let w=r.width,h=r.height,L=52,R=16,T=16,B=32,y=v=>h-B-v/max*(h-T-B),line=(values,color)=>{x.strokeStyle=color;x.lineWidth=2.5;x.beginPath();values.forEach((v,i)=>{let px=L+i/Math.max(1,values.length-1)*(w-L-R);i?x.lineTo(px,y(v)):x.moveTo(px,y(v))});x.stroke()};x.fillStyle='#fff';x.fillRect(0,0,w,h);for(let i=0;i<5;i++){let yy=T+i*(h-T-B)/4;x.strokeStyle='#dce7e2';x.beginPath();x.moveTo(L,yy);x.lineTo(w-R,yy);x.stroke();x.fillStyle='#5c7771';x.font='12px Inter';x.fillText((max*(1-i/4)).toFixed(1),4,yy+4)}line(D.actual,'#183e42');line(D.forecast,'#e08a3c')}addEventListener('resize',draw);draw();</script></html>'''
