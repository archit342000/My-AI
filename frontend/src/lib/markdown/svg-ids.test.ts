import { describe, expect, it } from 'vitest';
import { prefixSvgIds } from './svg-ids';

function svg(markup: string): SVGElement {
  const host = document.createElement('div');
  host.innerHTML = markup;
  return host.firstElementChild as SVGElement;
}

describe('prefixSvgIds', () => {
  it('renames every id and the references to it, in attributes and in style text', () => {
    const el = svg(
      '<svg id="m1"><style>#m1 .a{fill:red} #arrow{x:1}</style><defs><marker id="arrow"/></defs>' +
        '<path marker-end="url(#arrow)" href="#arrow"/></svg>',
    );
    prefixSvgIds(el, 'pop-');
    expect(el.id).toBe('pop-m1');
    expect(el.querySelector('marker')?.id).toBe('pop-arrow');
    expect(el.querySelector('path')?.getAttribute('marker-end')).toBe('url(#pop-arrow)');
    expect(el.querySelector('path')?.getAttribute('href')).toBe('#pop-arrow');
    expect(el.querySelector('style')?.textContent).toBe('#pop-m1 .a{fill:red} #pop-arrow{x:1}');
  });

  it('rewrites id tokens in aria-labelledby and aria-describedby', () => {
    const el = svg(
      '<svg id="c1" aria-labelledby="chart-title-c1" aria-describedby="chart-desc-c1 other"><title id="chart-title-c1">t</title><desc id="chart-desc-c1">d</desc></svg>',
    );
    prefixSvgIds(el, 'pop-');
    expect(el.getAttribute('aria-labelledby')).toBe('pop-chart-title-c1');
    expect(el.getAttribute('aria-describedby')).toBe('pop-chart-desc-c1 other');
    expect(el.querySelector('title')?.id).toBe('pop-chart-title-c1');
  });

  it('does not mix up an id that is a prefix of another or has regex characters', () => {
    const el = svg(
      '<svg id="a"><g id="a-b"/><g id="a.b"/><use href="#a-b"/><use href="#a.b"/><use href="#a"/></svg>',
    );
    prefixSvgIds(el, 'p-');
    const refs = Array.from(el.querySelectorAll('use')).map((u) => u.getAttribute('href'));
    expect(refs).toEqual(['#p-a-b', '#p-a.b', '#p-a']);
  });

  it('leaves an svg without ids alone', () => {
    const el = svg('<svg><g/></svg>');
    prefixSvgIds(el, 'pop-');
    expect(el.outerHTML).toBe('<svg><g></g></svg>');
  });
});
