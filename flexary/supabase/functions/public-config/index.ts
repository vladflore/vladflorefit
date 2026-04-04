Deno.serve((_req) => {
  const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
  const supabasePublishableKey = Deno.env.get("SUPABASE_PUBLISHABLE_KEY") ?? "";
  const enableSignIn = Deno.env.get("ENABLE_SIGN_IN") !== "false";

  const body = JSON.stringify({ supabaseUrl, supabasePublishableKey, enableSignIn });

  return new Response(body, {
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
    },
  });
});
