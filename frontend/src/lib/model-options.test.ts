import { describe, expect, it } from 'vitest';
import { displayModelName, isChatModel, modelDisplayNames, modelSelectOptions } from './model-options';

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

describe('modelDisplayNames', () => {
  const config = {
    research: { main: 'Qwen/Qwen3-30B-A3B' },
    general: {
      text: 'Google/Gemma4-26B-A4B-it',
      vision: 'Google/Gemma4-vis',
      vision2: 'Google/Gemma4-vis-hi',
      coder: 'Qwen/Qwen3-Coder',
      vision_small: 'Google/Gemma4-26B-A4B-it-small',
    },
  };

  it('names each role as the legacy picker does, with the last path segment of the id', () => {
    const names = modelDisplayNames(config);
    expect(names.get('Qwen/Qwen3-30B-A3B')).toBe('Research Main (Qwen3-30B-A3B)');
    expect(names.get('Google/Gemma4-26B-A4B-it')).toBe('General Text (Gemma4-26B-A4B-it)');
    expect(names.get('Google/Gemma4-vis')).toBe('General Vision (Gemma4-vis)');
    expect(names.get('Google/Gemma4-vis-hi')).toBe('General Vision (High) (Gemma4-vis-hi)');
    expect(names.get('Qwen/Qwen3-Coder')).toBe('General Coder (Qwen3-Coder)');
    expect(names.get('Google/Gemma4-26B-A4B-it-small')).toBe('Vision_small (Gemma4-26B-A4B-it-small)');
  });

  it('keeps the general name when a model is listed in both groups, and skips non-strings', () => {
    const names = modelDisplayNames({
      research: { main: 'x/Same' },
      general: { text: 'x/Same', bad: 3 as unknown as string },
    });
    expect(names.get('x/Same')).toBe('General Text (Same)');
    expect(names.size).toBe(1);
  });

  it('falls back to the id for an unknown model, and for an id without a path', () => {
    const names = modelDisplayNames({ general: { text: 'plain' } });
    expect(displayModelName('other/model', names)).toBe('other/model');
    expect(names.get('plain')).toBe('General Text (plain)');
  });
});
