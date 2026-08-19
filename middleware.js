// HTTP Basic Auth for the GAPS calendar.
// Added 2026-08-17. Credentials: gaps / fall2026
//
// Runs on Vercel's Edge before any file is served, so index.html is never
// reachable without credentials. This is real protection, not a JS gate.

export const config = {
  matcher: '/((?!_vercel).*)',
};

const USER = 'gaps';
const PASS = 'fall2026';

export default function middleware(request) {
  const header = request.headers.get('authorization') || '';
  const [scheme, encoded] = header.split(' ');

  if (scheme === 'Basic' && encoded) {
    let decoded = '';
    try {
      decoded = atob(encoded);
    } catch (e) {
      decoded = '';
    }
    const i = decoded.indexOf(':');
    if (i !== -1) {
      const user = decoded.slice(0, i);
      const pass = decoded.slice(i + 1);
      if (user === USER && pass === PASS) {
        return; // authorised, continue to the static file
      }
    }
  }

  return new Response('Authentication required.', {
    status: 401,
    headers: {
      'WWW-Authenticate': 'Basic realm="GAPS Calendar", charset="UTF-8"',
      'Content-Type': 'text/plain',
    },
  });
}
