import { SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY } from "./supabase-config.js";

const WORKOUTS_ENDPOINT = `${SUPABASE_URL}/functions/v1/workouts`;

async function workoutRequest(path, options = {}) {
  const { method = "GET", body } = options;

  const token = await window.flexaryAuth.getAccessToken();
  if (!token) throw new Error("Not authenticated");

  const response = await fetch(`${WORKOUTS_ENDPOINT}${path}`, {
    method,
    headers: {
      apikey: SUPABASE_PUBLISHABLE_KEY,
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const message =
      payload?.error || `Workout API request failed with status ${response.status}`;
    throw new Error(message);
  }

  return payload;
}

// Fetch all workouts for the authenticated user.
async function getWorkouts() {
  const payload = await workoutRequest("");
  return payload?.workouts ?? [];
}

// Upsert a single workout. The workout object must have an `id` field.
async function saveWorkout(workout) {
  if (!workout?.id) throw new Error("Workout must have an id");
  return workoutRequest(`/${workout.id}`, { method: "PUT", body: workout });
}

// Remove a single workout by its ID.
async function deleteWorkout(workoutId) {
  return workoutRequest(`/${workoutId}`, { method: "DELETE" });
}

window.flexaryWorkoutApi = {
  getWorkouts,
  saveWorkout,
  deleteWorkout,
};
