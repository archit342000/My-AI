const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '..', '..', 'static', 'js', 'icons.js'), 'utf8');
const sandbox = { window: {}, console };
const vm = require('vm');
vm.runInNewContext(src, sandbox);
const icons = sandbox.window.WORKSPACE_ICONS;
if (!icons) throw new Error('WORKSPACE_ICONS not found');
const entries = Object.entries(icons).map(([k, v]) => {
  const { paths, viewBox, ...rest } = v;
  return `  ${JSON.stringify(k)}: { paths: ${JSON.stringify(paths)} },`;
});
const out = `// Generated from static/js/icons.js (WORKSPACE_ICONS). Do not edit by hand.
// Regenerate with: node frontend/scripts/gen-icons.cjs.
export const WORKSPACE_ICON_PATHS: Record<string, { paths: string }> = {
${entries.join('\n')}
};
`;
fs.writeFileSync(path.join(__dirname, '..', 'src', 'components', 'icons', 'workspace-icons.generated.ts'), out);
console.log('icons:', Object.keys(icons).length);
