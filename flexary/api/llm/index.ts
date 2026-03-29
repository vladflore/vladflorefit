import type { LLMProvider } from './base';
import { OpenAIProvider } from './openai';
import { AnthropicProvider } from './anthropic';
import { OllamaProvider } from './ollama';

export function getProvider(): LLMProvider {
  const provider = (process.env.LLM_PROVIDER ?? 'openai').toLowerCase();
  if (provider === 'openai') return new OpenAIProvider();
  if (provider === 'anthropic') return new AnthropicProvider();
  if (provider === 'ollama') return new OllamaProvider();
  throw new Error(`Unknown LLM_PROVIDER: '${provider}'. Choose 'openai', 'anthropic', or 'ollama'.`);
}
