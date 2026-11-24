// TCP pass-through 0.0.0.0:EDGE_PORT -> 127.0.0.1:UPSTREAM_PORT. web/server.mjs listens on loopback only, so inside the
// shared network namespace of app.yml this is what the ALB (or a published port) reaches. No HTTP parsing: SSE and
// keep-alive go through as they are.
import { connect, createServer } from 'node:net'

const EDGE = Number(process.env.EDGE_PORT ?? 8080)
const UP = Number(process.env.UPSTREAM_PORT ?? 28899)

createServer((client) => {
  const up = connect(UP, '127.0.0.1')
  client.pipe(up).pipe(client)
  up.on('error', () => client.destroy())
  client.on('error', () => up.destroy())
}).listen(EDGE, '0.0.0.0', () => console.log(`edge 0.0.0.0:${EDGE} -> 127.0.0.1:${UP}`))
