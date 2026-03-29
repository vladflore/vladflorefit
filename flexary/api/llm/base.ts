export interface LLMProvider {
  describeWorkout(workout: Record<string, unknown>): Promise<string>;
}

type Exercise = {
  name?: string;
  sets?: number | string;
  reps?: string;
  time?: string;
  distance?: string;
  notes?: string;
  superset_id?: string;
};

export function buildPrompt(workout: Record<string, unknown>): string {
  const name = (workout.name as string) || 'Unnamed workout';
  const date = (workout.execution_date as string) || '';
  const exercises = (workout.exercises as Exercise[]) || [];
  const supersetRounds = (workout.superset_rounds as Record<string, number>) || {};

  const lines = exercises.map((ex) => {
    let line = `- ${ex.name}`;
    if (ex.superset_id) {
      const rounds = supersetRounds[ex.superset_id] ?? 1;
      const details = [ex.reps && `${ex.reps} reps`, ex.time, ex.distance].filter(Boolean).join(', ');
      line += ` [${details}] — part of superset (${rounds} rounds)`;
    } else {
      const details = [ex.reps && `${ex.reps} reps`, ex.time, ex.distance].filter(Boolean).join(', ');
      line += `: ${ex.sets} sets` + (details ? ` × ${details}` : '');
    }
    if (ex.notes) line += ` (note: ${ex.notes})`;
    return line;
  });

  return `You are an experienced fitness trainer writing a workout brief for a client.

Given the workout below, write a 1 paragraph description that:
- Explains what the session targets and why it's structured this way
- Highlights the key movements and their benefits
- Do not use complicated terminology

A couple of succint sentences is enough.

Workout name: ${name}
Scheduled for: ${date}

Exercises:
${lines.length ? lines.join('\n') : 'No exercises listed.'}

Write in second person ("you"), professionally but energetically. Do not repeat the exercise list verbatim.`;
}
