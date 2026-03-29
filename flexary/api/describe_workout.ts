import type { VercelRequest, VercelResponse } from '@vercel/node';
import { getProvider } from './llm/index';

export default async function handler(req: VercelRequest, res: VercelResponse) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(204).end();
  }
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const provider = process.env.LLM_PROVIDER ?? 'openai';
    console.log(`[describe_workout] provider=${provider}`);
    const description = await getProvider().describeWorkout(req.body);
    return res.status(200).json({ description });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const cause = error instanceof Error && (error as any).cause;
    console.error('[describe_workout] error:', error);
    return res.status(500).json({
      error: message,
      ...(cause ? { cause: String(cause) } : {}),
    });
  }
}
