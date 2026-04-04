const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

Deno.serve((req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  const enableSignIn = Deno.env.get("ENABLE_SIGN_IN") !== "false";

  const body = JSON.stringify({ enableSignIn });

  return new Response(body, {
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
});
