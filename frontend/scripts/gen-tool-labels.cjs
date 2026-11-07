// Generates src/features/chat/tool-labels.generated.ts from legacy static/js/constants.js
// (TOOL_DISPLAY_CONFIG). Run: node frontend/scripts/gen-tool-labels.cjs
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const src = fs.readFileSync(path.join(__dirname, '..', '..', 'static', 'js', 'constants.js'), 'utf8');
const config = vm.runInNewContext(`${src}\n;TOOL_DISPLAY_CONFIG`, { window: {}, console });
const lines = Object.entries(config).map(([k, v]) => `  ${JSON.stringify(k)}: ${JSON.stringify(v.name)},`);
const out = `// Generated from static/js/constants.js (TOOL_DISPLAY_CONFIG). Do not edit by hand.
// Regenerate with: node frontend/scripts/gen-tool-labels.cjs
export const TOOL_LABELS: Record<string, string> = {
${lines.join('\n')}
};
`;
fs.writeFileSync(path.join(__dirname, '..', 'src', 'features', 'chat', 'tool-labels.generated.ts'), out);
console.log('tools:', lines.length);
