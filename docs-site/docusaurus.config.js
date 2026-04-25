module.exports = {
  title: 'Balatro Agent API',
  tagline: 'Deterministic Mod-Assisted Solver',
  url: 'https://localhost',
  baseUrl: '/',
  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',
  organizationName: 'AI', 
  projectName: 'balatro-agent',
  presets: [['@docusaurus/preset-classic', { docs: { sidebarPath: require.resolve('./sidebars.js'), routeBasePath: '/' }}]],
  markdown: { mermaid: true },
  themes: ['@docusaurus/theme-mermaid'],
};
