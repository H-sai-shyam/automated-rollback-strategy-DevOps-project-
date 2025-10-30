const express = require('express');
const client = require('prom-client');
const fs = require('fs');

const app = express();
const register = client.register;

const version = (fs.existsSync('./version.txt') ? fs.readFileSync('./version.txt','utf8').trim() : 'v1');

const httpRequestDurationMicroseconds = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method','route','code','version'],
  buckets: [0.01,0.05,0.1,0.3,0.5,1,2]
});
const httpErrors = new client.Counter({
  name: 'http_errors_total',
  help: 'Total number of HTTP error responses',
  labelNames: ['route','version']
});

app.get('/', async (req,res) => {
  const end = httpRequestDurationMicroseconds.startTimer({method:'GET', route:'/', code:200, version});
  // simulate slightly higher latency in v2 to cause alerts
  const delay = version === 'v2' ? 600 : 50; // ms
  await new Promise(r => setTimeout(r, delay));
  end();
  res.send(`Hello from app ${version}\n`);
});

app.get('/simulate_error', (req,res) => {
  httpErrors.inc({route:'/simulate_error', version});
  res.status(500).send(`Simulated error on ${version}\n`);
});

app.get('/metrics', async (req,res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`App ${version} listening on ${PORT}`);
});
