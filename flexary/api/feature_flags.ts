import type { VercelRequest, VercelResponse } from '@vercel/node';

export default function handler(req: VercelRequest, res: VercelResponse) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.status(200).json({
    describe_workout: process.env.DESCRIBE_WORKOUT_ENABLED === 'true',
  });
}
