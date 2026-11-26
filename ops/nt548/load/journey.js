// k6 user journey for the scale numbers of docs/nt548/03-canary-scale.md: open the page, the signed-out check,
// a few API reads. Each virtual user keeps one tg_session cookie, as a browser would (sticky in nginx).
//   docker run --rm --network host -v $PWD/ops/nt548/load:/s grafana/k6 run -e BASE=http://127.0.0.1:8080 -e VUS=20 /s/journey.js
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE || 'http://127.0.0.1:8080';

export const options = {
  vus: Number(__ENV.VUS || 20),
  duration: __ENV.DURATION || '20s',
  summaryTrendStats: ['avg', 'med', 'p(95)', 'max'],
};

// 401 on /api/harness/me is the signed-out answer, not a failure
http.setResponseCallback(http.expectedStatuses({ min: 200, max: 399 }, 401));

export default function () {
  const params = { cookies: { tg_session: `k6-vu-${__VU}` }, headers: { 'Content-Type': 'application/json' } };
  const page = http.get(`${BASE}/`, params);
  check(page, { 'page 200': (r) => r.status === 200 });
  http.get(`${BASE}/api/harness/me`, params);
  const v = http.get(`${BASE}/api/harness/nt548-version`, params);
  check(v, { 'version 200': (r) => r.status === 200 });
  http.post(`${BASE}/api/harness/journeys`, '{}', params);
  sleep(Number(__ENV.THINK || 0.2));
}
