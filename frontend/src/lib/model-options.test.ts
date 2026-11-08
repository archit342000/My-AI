import { describe, expect, it } from 'vitest';
import { isChatModel, modelSelectOptions } from './model-options';

describe('model picker options (F-25)', () => {
  it('hides non-chat models from the chat list', () => {
    expect(isChatModel('Qwen3.5-4B')).toBe(true);
    expect(isChatModel('embeddinggemma-300m')).toBe(false);
    expect(isChatModel('Nomic-Embedding-v1')).toBe(false);
    expect(isChatModel('placeholder')).toBe(false);
    expect(isChatModel('default')).toBe(false);
  });

  it('orders loaded models first and puts non-chat models under Other', () => {
    const options = modelSelectOptions([
      { id: 'embeddinggemma', status: { value: 'loaded' } },
      { id: 'b-model', status: { value: 'unloaded' } },
      { id: 'a-model', status: { value: 'loading' } },
      { id: 'c-model', status: { value: 'loaded' } },
    ]);
    expect(options.map((o) => o.value)).toEqual(['c-model', 'embeddinggemma', 'a-model', 'b-model']);
    expect(options[1]!.group).toBe('Other');
    expect(options[0]!.group).toBeUndefined();
  });

  it('maps status to a dot tone', () => {
    const [loaded, loading, unloaded] = modelSelectOptions([
      { id: 'a', status: { value: 'loaded' } },
      { id: 'b', status: { value: 'loading' } },
      { id: 'c', status: { value: 'unloaded' } },
    ]);
    expect(loaded!.dot).toBe('success');
    expect(loading!.dot).toBe('warning');
    expect(unloaded!.dot).toBe('off');
  });
});
