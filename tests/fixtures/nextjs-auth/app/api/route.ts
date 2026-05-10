/**
 * Placeholder for other API routes.
 */
export async function GET(): Promise<Response> {
  return new Response(JSON.stringify({ status: "ok" }), { status: 200 });
}
