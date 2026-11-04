import { mergeConfig } from 'vite'
import base from './vite.config'

// A dev server you can sign in on: the harness accepts a POST only when its Origin matches APP_BASE_URL or the Host it sees, and the
// stock proxy rewrites Host to the harness (changeOrigin). Here the browser's Host passes through, so a guest or email login from
// http://localhost:<port> works against the running harness. Open it as `localhost` (a port forward is fine): the session cookie is
// Secure, which browsers only accept over https or localhost.
// Run: cd web && npx vite --config vite.preview.config.ts --port <free port> --strictPort
const to = (port: string | number) => ({ target: `http://127.0.0.1:${port}`, changeOrigin: false })

export default mergeConfig(base, {
  server: {
    proxy: {
      '/api/harness': to(process.env.HARNESS_PORT ?? 8769),
      '/api/auth': to(process.env.HARNESS_PORT ?? 8769),
    },
  },
})
