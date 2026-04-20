import { createClient } from "jsr:@supabase/supabase-js@2";
import { createRemoteJWKSet, jwtVerify } from "npm:jose@5";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY")!;

// Cached at module level — fetched once per function instance, refreshed
// automatically by jose when keys rotate.
const jwks = createRemoteJWKSet(
  new URL(`${SUPABASE_URL}/auth/v1/.well-known/jwks.json`),
);

const ALLOWED_ORIGINS = new Set([
  "https://vladflore.fit",
  "http://127.0.0.1:5500",
]);

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function corsHeaders(origin: string | null): Record<string, string> {
  const allowed =
    origin && ALLOWED_ORIGINS.has(origin) ? origin : "https://vladflore.fit";
  return {
    "Access-Control-Allow-Origin": allowed,
    "Access-Control-Allow-Methods": "GET, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, apikey",
    "Vary": "Origin",
  };
}

function json(body: unknown, headers: Record<string, string>, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...headers, "Content-Type": "application/json" },
  });
}

// Verify the JWT signature and claims locally using Supabase's public JWKS.
// Returns the user ID on success, null on any failure — always fails closed.
async function verifyToken(token: string): Promise<string | null> {
  try {
    const { payload } = await jwtVerify(token, jwks, {
      issuer: `${SUPABASE_URL}/auth/v1`,
      audience: "authenticated",
    });
    return typeof payload.sub === "string" ? payload.sub : null;
  } catch {
    return null;
  }
}

Deno.serve(async (req) => {
  const origin = req.headers.get("Origin");
  const cors = corsHeaders(origin);

  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: cors });
  }

  const authHeader = req.headers.get("Authorization");
  if (!authHeader) return json({ error: "Unauthorized" }, cors, 401);

  const token = authHeader.replace(/^Bearer\s+/i, "");
  const userId = await verifyToken(token);
  if (!userId) return json({ error: "Unauthorized" }, cors, 401);

  // Create the DB client with the user's JWT so RLS policies are enforced.
  const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    global: { headers: { Authorization: authHeader } },
  });

  // Extract optional workout ID from the path: /functions/v1/workouts[/:id]
  const url = new URL(req.url);
  const segments = url.pathname.split("/").filter(Boolean);
  const lastSegment = segments.at(-1);
  const workoutId = lastSegment !== "workouts" ? lastSegment : null;

  if (workoutId && !UUID_RE.test(workoutId)) {
    return json({ error: "Invalid workout ID" }, cors, 400);
  }

  // GET /workouts — fetch all workouts for the authenticated user
  if (req.method === "GET" && !workoutId) {
    const { data, error } = await supabase
      .from("workouts")
      .select("data, updated_at")
      .order("updated_at", { ascending: false });

    if (error) return json({ error: error.message }, cors, 500);

    return json({ workouts: data.map((row) => row.data) }, cors);
  }

  // PUT /workouts/:id — upsert a single workout
  if (req.method === "PUT" && workoutId) {
    const body = await req.json();
    // Overwrite data.id with the authoritative path ID to prevent divergence.
    body.id = workoutId;

    const { error } = await supabase.from("workouts").upsert({
      id: workoutId,
      user_id: userId,
      data: body,
    });

    if (error) return json({ error: error.message }, cors, 500);

    return json({ ok: true }, cors);
  }

  // DELETE /workouts/:id — remove a single workout
  if (req.method === "DELETE" && workoutId) {
    const { error } = await supabase
      .from("workouts")
      .delete()
      .eq("id", workoutId);

    if (error) return json({ error: error.message }, cors, 500);

    return json({ ok: true }, cors);
  }

  return json({ error: "Not found" }, cors, 404);
});
