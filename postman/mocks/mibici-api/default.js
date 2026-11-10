// Contrato de api/main.py. Solo se usa para verificar el cliente HTTP de auditoría.
// No ejecuta MLflow ni acredita inferencia o ejecución en contenedor.
const http = require('node:http');
const fields = ['capacity','latitude','longitude','salidas_lag_1','llegadas_lag_1','salidas_lag_2','llegadas_lag_2','salidas_lag_24','llegadas_lag_24','salidas_lag_168','llegadas_lag_168','balance_rolling_3h','balance_rolling_12h','sin_hour','cos_hour','sin_dow','cos_dow'];
http.createServer((req, res) => {
  res.setHeader('content-type', 'application/json');
  const send = (code, body) => { res.statusCode = code; res.end(JSON.stringify(body)); };
  const path = new URL(req.url, 'http://localhost').pathname;
  if (req.method === 'GET' && path === '/') return send(200, {status: 'ok', model: 'mibici-equipo30-p2-riesgo'});
  if (req.method === 'GET' && path === '/health') return send(200, {status: 'healthy', version: '1.0.0'});
  if (req.method === 'GET' && path === '/model-info') return send(200, {model_uri: 'models:/mibici-equipo30-p2-riesgo@champion'});
  if (req.method !== 'POST' || path !== '/predict') return send(501, {detail: 'Ruta fuera del alcance de esta simulación'});
  const body = req.body || {};
  const badKeys = fields.some(key => !(key in body)) || Object.keys(body).some(key => !fields.includes(key));
  const badNumber = fields.some(key => typeof body[key] !== 'number' || !Number.isFinite(body[key]) || Math.abs(body[key]) > 3.4028234663852886e38);
  const badCapacity = !Number.isInteger(body.capacity) || body.capacity <= 0 || body.capacity > 2147483647;
  const badRange = fields.some(key => (key.includes('_lag_') && body[key] < 0) || ((key.startsWith('sin_') || key.startsWith('cos_')) && Math.abs(body[key]) > 1));
  const badCoordinates = Math.abs(body.latitude) > 90 || Math.abs(body.longitude) > 180;
  if (badKeys || badNumber || badCapacity || badRange || badCoordinates) return send(422, {detail: [{type: 'validation_error', msg: 'Entrada fuera del contrato'}]});
  return send(200, {prediction: 2});
}).listen(process.env.PORT || 4500);
