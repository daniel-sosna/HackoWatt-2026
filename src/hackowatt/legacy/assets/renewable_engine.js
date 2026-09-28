/* Pure calculation functions. All energy arrays are kWh per physical hour. */
const EnergyEngine = (() => {
  const sum = values => values.reduce((a, b) => a + b, 0);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  function price(hour, s) {
    return hour < 6 ? s.nightPrice : hour < 17 ? s.dayPrice : hour < 22 ? s.peakPrice : s.latePrice;
  }
  function balance(load, pv, prices, sell) {
    const imports = load.map((v, i) => Math.max(0, v - pv[i]));
    const exports = pv.map((v, i) => Math.max(0, v - load[i]));
    const self = load.map((v, i) => Math.min(v, pv[i]));
    return {load: sum(load), pv: sum(pv), imp: sum(imports), exp: sum(exports), self: sum(self),
      cost: sum(imports.map((v, i) => v * prices[i] - exports[i] * sell)),
      peak: Math.max(0, ...imports), imports, exports};
  }
  function objective(load, pv, prices, s) {
    let money = 0, imported = 0, excess = 0;
    for (let i = 0; i < load.length; i++) {
      const grid = Math.max(0, load[i] - pv[i]);
      money += grid * prices[i] - Math.max(0, pv[i] - load[i]) * s.exportPrice;
      imported += grid;
      excess += Math.max(0, grid - s.gridLimit) ** 2;
    }
    return s.goal === 'solar' ? imported * 1000 + money : s.goal === 'grid' ? excess * 1000 + money : money;
  }
  function schedule(d, s) {
    const load = d.loadKwh.slice(), pv = d.pvKwhPerKwpAt1000Yield.map(v => v * s.capacity * s.specificYield / 1000);
    const prices = d.localHour.map(h => price(h, s)), reservations = {}, changes = [], retained = [];
    const events = d.flexibleEvents.filter(e => !e.proxy).map((e, id) => ({...e, id}));
    // Reserve all original cycles, including disabled devices, before moving any cycle.
    for (const e of events) {
      const begin = e.startIndex * 60 + (e.startMinute || 0);
      (reservations[e.resource] ||= []).push({id:e.id, start:begin, end:begin + e.durationMinutes});
    }
    for (const ev of events) {
      const cfg = s.devices[ev.category];
      if (!cfg?.enabled || s.locked.includes(ev.id)) continue;
      // TV/console co-use remains together. A screen run overlapping gaming is locked.
      if (ev.category === 'tv' && events.some(e => e.resource !== ev.resource && e.category === 'tv' &&
        e.startIndex * 60 + (e.startMinute || 0) < ev.startIndex * 60 + (ev.startMinute || 0) + ev.durationMinutes &&
        ev.startIndex * 60 + (ev.startMinute || 0) < e.startIndex * 60 + (e.startMinute || 0) + e.durationMinutes)) continue;
      const original = ev.startIndex, minute = ev.startMinute || 0, profile = ev.profile;
      for (let j=0; j<profile.length && original+j<load.length; j++) load[original+j] -= profile[j];
      const evaluate = start => {
        let money=0, imp=0, excess=0;
        for(let j=0;j<profile.length;j++) {
          const i=start+j, before=Math.max(0,load[i]-pv[i]), after=Math.max(0,load[i]+profile[j]-pv[i]);
          money += (after-before)*prices[i] + (Math.max(0,pv[i]-load[i])-Math.max(0,pv[i]-load[i]-profile[j]))*s.exportPrice;
          imp += after-before;
          excess += Math.max(0,after-s.gridLimit)**2-Math.max(0,before-s.gridLimit)**2;
        }
        return {money, score:s.goal==='solar'?imp*1000+money:s.goal==='grid'?excess*1000+money:money};
      };
      let best=original, before=evaluate(original), chosen=before, candidates=0;
      for(let shift=-cfg.shift;shift<=cfg.shift;shift++) {
        const start=original+shift, stop=start+profile.length;
        if(start<0||stop>load.length||d.localDate[start]!==d.localDate[original])continue;
        const h=d.localHour[start]+minute/60, end=h+ev.durationMinutes/60;
        if(h<cfg.earliest||end>cfg.latest)continue;
        if(['cooking','tv','computer'].includes(ev.category) &&
          profile.some((_, j)=>s.occupancy[d.localDayType[start+j]][d.localHour[start+j]]<=0))continue;
        const begin=start*60+minute, finish=begin+ev.durationMinutes;
        if(reservations[ev.resource].some(r=>r.id!==ev.id&&begin<r.end&&r.start<finish))continue;
        candidates++;
        const candidate=evaluate(start);
        if(candidate.score<chosen.score-1e-8 || (Math.abs(candidate.score-chosen.score)<1e-8 && Math.abs(start-original)<Math.abs(best-original))) {
          best=start; chosen=candidate;
        }
      }
      for(let j=0;j<profile.length&&best+j<load.length;j++)load[best+j]+=profile[j];
      const reserved=reservations[ev.resource].find(r=>r.id===ev.id);
      reserved.start=best*60+minute;reserved.end=reserved.start+ev.durationMinutes;
      if(best!==original)changes.push({...ev,from:original,to:best,saving:before.money-chosen.money,
        reason:s.goal==='grid'?'Less load above your grid limit':s.goal==='solar'?'More solar used in your home':prices[best]<prices[original]?'Lower electricity price':'More solar available'});
      else if(!candidates)retained.push(ev.id);
    }
    return {load:load.map(v=>Math.max(0,v)),pv,prices,changes,retained};
  }
  function investment(d,s,plan) {
    const years=d.yearCount, zero=Array(d.loadKwh.length).fill(0);
    const a=balance(d.loadKwh,plan.pv,plan.prices,s.exportPrice), b=balance(plan.load,plan.pv,plan.prices,s.exportPrice);
    const baseline=balance(d.loadKwh,zero,plan.prices,s.exportPrice), capex=s.capacity*s.capex;
    const grant=Math.min(capex,s.subsidy), net=(capex-grant)*(1-s.tax/100), opex=capex*s.opex/100;
    const saveA=(baseline.cost-a.cost)/years-opex, saveB=(baseline.cost-b.cost)/years-opex;
    const pay=v=>s.capacity<=0?null:v>0?net/v:Infinity;
    return {a,b,baseline,capex,net,opex,saveA,saveB,payA:pay(saveA),payB:pay(saveB),years};
  }
  function lifetime(d,s,plan,inv) {
    const cashA=[-inv.net],cashB=[-inv.net];let a=-inv.net,b=-inv.net,discA=null,discB=null;
    const zero=Array(d.loadKwh.length).fill(0);
    for(let year=1;year<=s.horizon;year++) {
      const rate=(1+s.growth/100)**(year-1), pv=plan.pv.map(v=>v*(1-s.degradation/100)**(year-1));
      const prices=plan.prices.map(v=>v*rate),base=balance(d.loadKwh,zero,prices,s.exportPrice*rate);
      const repl=year===s.inverterYear?inv.capex*s.inverterCost/100:0;
      const costs=inv.opex*rate+repl,discount=(1+s.discount/100)**year;
      a+=((base.cost-balance(d.loadKwh,pv,prices,s.exportPrice*rate).cost)/d.yearCount-costs)/discount;
      b+=((base.cost-balance(plan.load,pv,prices,s.exportPrice*rate).cost)/d.yearCount-costs)/discount;
      cashA.push(a);cashB.push(b);if(a>=0&&discA===null)discA=year;if(b>=0&&discB===null)discB=year;
    }
    return {cashA,cashB,npvA:a,npvB:b,discA,discB};
  }
  const presets={comfort:{home:21,away:18.5,sleep:19},balanced:{home:20.5,away:17.5,sleep:18.5},saving:{home:20,away:17,sleep:18}};
  function rc(temp,out,gain,H,C,dt){const decay=Math.exp(-H*dt/C);return out+(temp-out)*decay+gain/H*(1-decay)}
  function thermal(f,model,s) {
    if(!f?.available||!model?.available||!f.thermalInputsAvailable)return null;
    const h=model.house,ts=model.settings,p=presets[s.comfort],N=Math.min(24,f.loadKwh.length);
    const pv=f.pvKwhPerKwpAt1000Yield.slice(0,N).map(v=>v*s.capacity*(f.pvIsProvider?1:s.specificYield/1000));
    const nonthermal=f.loadKwh.slice(0,N).map((v,i)=>Math.max(0,v-f.spaceHeatingKwh[i]-f.waterHeatingKwh[i]));
    const start={room:s.indoor,tank:s.tank,heatOn:false,tankOn:false};
    function advance(state,i,action) {
      const hour=f.localHour[i],people=s.occupancy[f.localDayType[i]][hour],sleep=hour<6||hour>=23;
      const minRoom=people? (sleep?p.sleep:p.home):p.away, maxRoom=s.roomMax, minTank=s.tankMin, maxTank=s.tankMax;
      let {room,tank,heatOn,tankOn}=state,heatKwh=0,tankKwh=0,violation=0,unmet=0,minSeen=room,minTankSeen=tank;
      const date=new Date(f.timestampUtc[i]),month=date.getUTCMonth()+1;
      const day=Math.floor((date-Date.UTC(date.getUTCFullYear(),0,0))/86400000),mains=10+5*Math.sin(2*Math.PI*(day-120)/365.25);
      const C=h.floor_area_m2*h.thermal_capacity_wh_m2k/1000, Ct=h.tank_volume_l*.001163, dt=.25;
      for(let j=0;j<4;j++) {
        const draw=f.hotWaterDrawL[i]/4, demand=draw*.001163*Math.max(0,h.water_use_temperature_c-mains),old=tank;
        const reserve=Math.max(0,(tank-h.water_use_temperature_c)*Ct);
        if(demand<=reserve)tank-=demand/Ct;
        else {const remaining=Math.max(0,draw-reserve/Math.max(1e-9,.001163*(h.water_use_temperature_c-mains)));tank=mains+(Math.min(tank,h.water_use_temperature_c)-mains)*Math.exp(-remaining/h.tank_volume_l)}
        unmet+=Math.max(0,demand-Math.max(0,(old-tank)*Ct));
        minTankSeen=Math.min(minTankSeen,tank);
        if(room<minRoom+h.thermostat_deadband_c/2)heatOn=true;
        else if(room>minRoom+h.thermostat_deadband_c*1.5)heatOn=false;
        if(tank<h.tank_setpoint_c-h.tank_deadband_c)tankOn=true;else if(tank>=h.tank_setpoint_c)tankOn=false;
        const heating=(action?action[0]:Number(heatOn))*h.heating_capacity_kw;
        const boiler=(action?action[1]:Number(tankOn))*h.boiler_power_kw;
        const before=tank;tank=rc(tank,room,boiler,h.tank_loss_w_k/1000,Ct,dt);
        const tankGain=boiler-(tank-before)*Ct/dt;
        let ach=h.air_changes_per_hour+h.wind_ach_per_ms*f.windMs[i];
        if(people&&!sleep&&room>h.window_open_above_c&&f.outdoorC[i]<room)ach+=h.window_open_ach;
        const vent=ts.night_ventilation||{};
        if(vent.enabled&&vent.months.includes(month)&&(hour>=vent.start_hour||hour<vent.end_hour)&&people&&room>=vent.minimum_indoor_c&&f.outdoorC[i]<=room-vent.minimum_outdoor_delta_c)ach+=vent.additional_ach;
        const H=(h.floor_area_m2*h.fabric_loss_w_m2k+.33*h.floor_area_m2*h.height_m*ach)/1000;
        const solar=h.effective_solar_area_m2*f.solarRadiationWm2[i]*(month>=5&&month<=9?.35:1)/1000;
        const internal=people*(sleep?ts.person_sleep_w:ts.person_awake_w)/1000+nonthermal[i]*ts.internal_electric_gain_fraction+tankGain;
        room=rc(room,f.outdoorC[i],heating*h.heating_efficiency+solar+internal,H,C,dt);
        minSeen=Math.min(minSeen,room);heatKwh+=heating*dt;tankKwh+=boiler*dt;
        violation+= (Math.max(0,minRoom-room)+Math.max(0,room-maxRoom)+Math.max(0,minTank-tank)+Math.max(0,tank-maxTank))*dt;
      }
      violation+=Math.max(0,minTank-minTankSeen)*.25+unmet*10;
      const load=nonthermal[i]+heatKwh+tankKwh,grid=Math.max(0,load-pv[i]);
      const cost=grid*price(hour,s)-Math.max(0,pv[i]-load)*s.exportPrice;
      const score=s.goal==='solar'?grid*1000+cost:s.goal==='grid'?Math.max(0,grid-s.gridLimit)**2*1000+cost:cost;
      return {state:{room,tank,heatOn,tankOn},room,tank,heatKwh,tankKwh,load,grid,cost,score,violation,minSeen,minTankSeen,minRoom,unmet};
    }
    let st=start;const baseline=[];
    for(let i=0;i<N;i++){const q=advance(st,i,null);baseline.push(q);st=q.state}
    let beam=[{state:start,score:0,path:[]}],failed=false;
    const actions=[0,.5,1].flatMap(a=>[0,.5,1].map(b=>[a,b]));
    for(let i=0;i<N;i++){
      const candidates=[];
      for(const node of beam)for(const action of actions){const q=advance(node.state,i,action);if(q.violation>1e-6)continue;candidates.push({state:q.state,score:node.score+q.score,path:node.path.concat(q)})}
      if(!candidates.length){failed=true;break}
      candidates.sort((a,b)=>a.score-b.score);const unique=new Map();
      for(const q of candidates){const key=Math.round(q.state.room*10)+'|'+Math.round(q.state.tank*4);if(!unique.has(key))unique.set(key,q);if(unique.size>=120)break}beam=[...unique.values()];
    }
    const end=baseline[N-1];const finalists=failed?[]:beam.filter(q=>q.state.room>=end.room-.05&&q.state.tank>=end.tank-.05);
    const baselineValid=baseline.every(q=>q.violation<=1e-6);
    if(baselineValid)finalists.push({path:baseline,score:sum(baseline.map(q=>q.score))});
    finalists.sort((a,b)=>a.score-b.score);const path=finalists[0]?.path||baseline;
    const summarise=rows=>({cost:sum(rows.map(q=>q.cost)),imp:sum(rows.map(q=>q.grid)),peak:Math.max(...rows.map(q=>q.grid)),violations:rows.filter(q=>q.violation>1e-6).length,minRoom:Math.min(...rows.map(q=>q.minSeen)),minTank:Math.min(...rows.map(q=>q.minTankSeen))});
    return {baseline,path,before:summarise(baseline),after:summarise(path),feasible:finalists.length>0,pv,
      reason:finalists.length?'Model limits checked at 15-minute steps; terminal heat reserve preserved.':'No feasible plan found by the bounded search. Thermostat fallback shown; no comfort or savings claim.'};
  }
  return {sum,clamp,price,balance,schedule,investment,lifetime,thermal,presets,rc};
})();
if(typeof module!=='undefined')module.exports=EnergyEngine;
