// Owner-authorized, bounded capacity check against the *live* unpublished website.
// Designed to characterize degradation, NOT to generate uncontrolled DDoS traffic.
// k6 is run manually from a separate load-generation host (not GitHub Actions).
import http from 'k6/http';
import { check, sleep } from 'k6';

const TARGET = 'https://zedoneexam.site/';

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '30s', target: 25 },
    { duration: '30s', target: 50 },
    { duration: '15s', target: 0 },
  ],
  thresholds: {
    http_req_failed: [{
      threshold: 'rate<0.05',
      abortOnFail: true,
      delayAbortEval: '15s',
    }],
    http_req_duration: [{
      threshold: 'p(95)<3000',
      abortOnFail: true,
      delayAbortEval: '15s',
    }],
  },
  discardResponseBodies: true,
  maxRedirects: 3,
  userAgent: 'ZedOne-Authorized-Capacity-Test/1.0',
};

export default function () {
  const res = http.get(TARGET, { timeout: '10s' });
  check(res, { 'homepage returned HTTP 200': (r) => r.status === 200 });
  sleep(1 + Math.random());
}

// Run: k6 run security/vps-toolkit/scripts/zedone-live-capacity.js
// Keep an SSH session open for observation and emergency intervention.
// Stop manually with Ctrl+C if production resource use becomes unsafe.
// The root path might be served from a CDN or cache; success here does not
// establish backend, database, or exam-submission capacity.
