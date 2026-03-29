import OpenAI from 'openai';
import type { LLMProvider } from './base';
import { buildPrompt } from './base';

export class OllamaProvider implements LLMProvider {
  private client: OpenAI;
  private model: string;

  constructor() {
    const baseURL = (process.env.OLLAMA_BASE_URL ?? 'http://localhost:11434') + '/v1';
    this.model = process.env.OLLAMA_MODEL ?? 'llama3.3';
    this.client = new OpenAI({ baseURL, apiKey: 'ollama' });
  }

  async describeWorkout(workout: Record<string, unknown>): Promise<string> {
    const response = await this.client.chat.completions.create({
      model: this.model,
      messages: [{ role: 'user', content: buildPrompt(workout) }],
      max_tokens: 512,
      temperature: 0.7,
    });
    return response.choices[0].message.content ?? '';
  }
}
