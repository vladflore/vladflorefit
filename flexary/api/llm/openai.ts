import OpenAI from 'openai';
import type { LLMProvider } from './base';
import { buildPrompt } from './base';

export class OpenAIProvider implements LLMProvider {
  private client: OpenAI;

  constructor() {
    this.client = new OpenAI(); // reads OPENAI_API_KEY from env
  }

  async describeWorkout(workout: Record<string, unknown>): Promise<string> {
    const response = await this.client.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [{ role: 'user', content: buildPrompt(workout) }],
      max_tokens: 512,
      temperature: 0.7,
    });
    return response.choices[0].message.content ?? '';
  }
}
