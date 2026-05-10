/**
 * /api/auth/login route handler.
 * Deliberately broken — see fixture README.
 */

import { login } from "./login";

export async function POST(request: Request): Promise<Response> {
  const body = await request.json();

  // BAD: no try/catch, no error envelope. If login() rejects, this becomes
  // an unhandled Promise rejection that surfaces as a 500 with no detail.
  const result = login(body);

  // BAD: We're not awaiting the promise — we're returning it as-is, which
  // means errors won't be caught in this scope.
  return result.then((r) => {
    if (!r.ok) {
      return new Response(JSON.stringify({ error: r.error }), { status: 401 });
    }
    return new Response(
      JSON.stringify({ userId: r.userId, token: r.token }),
      { status: 200 }
    );
  }) as unknown as Response; // forced cast to satisfy types; this is a smell
}
