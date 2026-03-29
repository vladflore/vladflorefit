import Anthropic from '@anthropic-ai/sdk';
import type { LLMProvider } from './base';
import { buildPrompt } from './base';

export class AnthropicProvider implements LLMProvider {
  private client: Anthropic;

  constructor() {
    this.client = new Anthropic(); // reads ANTHROPIC_API_KEY from env
  }

  async describeWorkout(workout: Record<string, unknown>): Promise<string> {
    const message = await this.client.messages.create({
      model: 'claude-opus-4-6',
      max_tokens: 512,
      messages: [{ role: 'user', content: buildPrompt(workout) }],
    });
    const block = message.content[0];
    return block.type === 'text' ? block.text : '';
  }
}
