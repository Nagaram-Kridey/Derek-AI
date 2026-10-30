type Recommendation = { decision: string; reason: string };
const groups: [string[], Recommendation][] = [
  [['foundation', 'context', 'memory', 'research', 'reports', 'schedule', 'daily-projects', 'telegram', 'voice', 'runtime', 'backup', 'evals'], { decision: 'Keep and verify', reason: 'Supports everyday assistance or its reliability. Complete current acceptance before expanding scope; implemented does not mean verified live.' }],
  [['dashboard', 'models', 'workflows', 'files', 'browser', 'private', 'autologin', 'roadmap', 'whatsapp-web'], { decision: 'Simplify', reason: 'Preserve the capability and existing data. Reduce setup and navigation burden; keep permissions and action outcomes explicit.' }],
  [['calendar', 'observe', 'mouse', 'visual-agent', 'streaming', 'wakeword', 'installer', 'cloud', 'phone', 'custom-model', 'sandbox', 'flags', 'connectors', 'mobile', 'browser-extension'], { decision: 'Defer expansion', reason: 'Resume after core acceptance and any required owner setup. Retain the idea without adding runtime complexity now.' }],
  [['multiuser'], { decision: 'Archive from active scope', reason: 'Organizations and multiple users are outside Derek’s current single-owner purpose. Preserve the idea; no code or data is removed.' }],
];
const recommendations = new Map(groups.flatMap(([ids, value]) => ids.map(id => [id, value] as const)));
export function recommendationFor(id: string): Recommendation | undefined {
  return recommendations.get(id);
}
