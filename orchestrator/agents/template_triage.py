#!/usr/bin/env python3
"""
Template Triage Agent - Analyzes template/fork changes for sync opportunities
"""

import json
import logging
from typing import Dict, List
import anthropic
from github import Github

logger = logging.getLogger(__name__)


class TemplateTriageAgent:
    """
    Analyzes changes in a template repository and determines what should sync to derivatives.

    Use Case: vllm-container-ngc changes → should vllm-container-coder adopt them?
    """

    def __init__(self, anthropic_client: anthropic.Anthropic, github_client: Github):
        self.anthropic = anthropic_client
        self.github = github_client

    async def analyze(
        self,
        template_repo: str,
        derivative_repo: str,
        change_event: Dict,
        derivative_config: Dict
    ) -> Dict:
        """
        Analyze if template changes should propagate to derivative.

        Returns:
            {
                'requires_action': bool,
                'urgency': 'critical|high|medium|low',
                'impact_summary': str,
                'affected_files': [str],
                'recommended_changes': str,
                'confidence': float,
                'reasoning': str
            }
        """
        try:
            logger.info(f"Analyzing template sync: {template_repo} -> {derivative_repo}")

            # 1. Filter changes to shared concerns
            relevant_changes = self._filter_template_changes(
                change_event,
                derivative_config.get('shared_concerns', []),
                derivative_config.get('divergent_concerns', [])
            )

            if not relevant_changes['is_relevant']:
                return {
                    'requires_action': False,
                    'urgency': 'low',
                    'impact_summary': 'Changes are not in shared infrastructure areas',
                    'affected_files': [],
                    'recommended_changes': '',
                    'confidence': 0.9,
                    'reasoning': 'Changes only affect divergent concerns (application-specific logic)'
                }

            # 2. Fetch derivative's version of the changed files
            derivative_context = await self._fetch_derivative_context(
                derivative_repo,
                relevant_changes['relevant_files']
            )

            # 3. Use LLM to analyze sync opportunity
            analysis = await self._llm_analyze_sync(
                template_repo=template_repo,
                derivative_repo=derivative_repo,
                template_changes=change_event,
                relevant_changes=relevant_changes,
                derivative_context=derivative_context,
                derivative_config=derivative_config
            )

            return analysis

        except Exception as e:
            logger.error(f"Error in template triage analysis: {e}", exc_info=True)
            return {
                'requires_action': False,
                'urgency': 'low',
                'impact_summary': f'Error during analysis: {str(e)}',
                'affected_files': [],
                'recommended_changes': '',
                'confidence': 0.0,
                'reasoning': f'Analysis failed: {str(e)}'
            }

    def _filter_template_changes(
        self,
        change_event: Dict,
        shared_concerns: List[str],
        divergent_concerns: List[str]
    ) -> Dict:
        """
        Filter changes to those in shared infrastructure areas.

        Shared concerns: infrastructure, docker, deployment, gpu_configuration, health_checks
        Divergent concerns: application_logic, model_specific, api_endpoints
        """
        changed_files = change_event.get('changed_files', [])
        pattern_summary = change_event.get('pattern_summary', {})

        patterns = pattern_summary.get('patterns', [])
        keywords = pattern_summary.get('keywords', [])

        # Map shared concerns to file/keyword patterns
        concern_patterns = {
            'infrastructure': ['docker', 'compose', 'deploy', 'infra', 'terraform'],
            'docker': ['dockerfile', 'docker-compose', '.dockerignore', 'docker'],
            'deployment': ['deploy', 'k8s', 'kubernetes', 'helm', 'compose'],
            'gpu_configuration': ['gpu', 'cuda', 'nvidia', 'vram', 'device'],
            'health_checks': ['health', 'readiness', 'liveness', 'probe'],
            'logging': ['log', 'logger', 'logging', 'monitor'],
            'monitoring': ['monitor', 'metric', 'prometheus', 'grafana'],
        }

        # Map divergent concerns
        divergent_patterns = {
            'application_logic': ['app.py', 'main.py', 'service', 'business'],
            'model_specific': ['model', 'inference', 'generation', 'prompt'],
            'api_endpoints': ['endpoint', 'route', 'api/', 'handler'],
            'business_logic': ['business', 'logic', 'service', 'domain']
        }

        # Check which shared concerns match
        matched_shared = []
        for concern in shared_concerns:
            if concern in concern_patterns:
                concern_keywords = concern_patterns[concern]
                if any(kw in str(patterns + keywords).lower() for kw in concern_keywords):
                    matched_shared.append(concern)

        # Check which divergent concerns match (we want to AVOID these)
        matched_divergent = []
        for concern in divergent_concerns:
            if concern in divergent_patterns:
                concern_keywords = divergent_patterns[concern]
                if any(kw in str(patterns + keywords).lower() for kw in concern_keywords):
                    matched_divergent.append(concern)

        # Filter files
        relevant_files = []
        for file_info in changed_files:
            path = file_info.get('path', '').lower()

            # Check if file matches shared concerns
            is_shared = any(
                any(kw in path for kw in concern_patterns.get(concern, []))
                for concern in shared_concerns
            )

            # Check if file matches divergent concerns
            is_divergent = any(
                any(kw in path for kw in divergent_patterns.get(concern, []))
                for concern in divergent_concerns
            )

            # Include if shared and not divergent
            if is_shared and not is_divergent:
                relevant_files.append(file_info)

        # Relevant if we have shared matches and no/few divergent matches
        is_relevant = len(matched_shared) > 0 and len(matched_divergent) <= len(matched_shared)

        return {
            'is_relevant': is_relevant,
            'matched_shared_concerns': matched_shared,
            'matched_divergent_concerns': matched_divergent,
            'relevant_files': relevant_files
        }

    async def _fetch_derivative_context(self, derivative_repo: str, relevant_files: List[Dict]) -> Dict:
        """Fetch the derivative's current version of changed files"""
        context = {}

        try:
            repo = self.github.get_repo(derivative_repo)

            for file_info in relevant_files[:5]:  # Limit
                file_path = file_info.get('path', '')
                try:
                    content = repo.get_contents(file_path)
                    if content.size < 100000:  # Skip large files
                        context[file_path] = {
                            'content': content.decoded_content.decode('utf-8'),
                            'size': content.size,
                            'sha': content.sha
                        }
                except Exception as e:
                    logger.warning(f"Could not fetch {file_path} from derivative: {e}")
                    context[file_path] = {
                        'content': '<file not found>',
                        'note': f'May not exist in derivative: {e}'
                    }

        except Exception as e:
            logger.error(f"Error fetching derivative context: {e}")

        return context

    async def _llm_analyze_sync(
        self,
        template_repo: str,
        derivative_repo: str,
        template_changes: Dict,
        relevant_changes: Dict,
        derivative_context: Dict,
        derivative_config: Dict
    ) -> Dict:
        """Use Claude to determine if changes should sync"""

        # Prepare template changes summary
        files_summary = []
        for file_info in relevant_changes['relevant_files'][:10]:
            files_summary.append({
                'path': file_info.get('path', ''),
                'change_type': file_info.get('change_type', ''),
                'diff': file_info.get('diff', '')[:1500]
            })

        # Prepare derivative context
        derivative_summary = {}
        for path, info in derivative_context.items():
            derivative_summary[path] = {
                'content_preview': info.get('content', '')[:1500],
                'note': info.get('note', '')
            }

        prompt = f"""You are analyzing changes in a template repository to determine if they should propagate to a derivative (fork).

**Template Repository (Source)**: {template_repo}
**Derivative Repository (Target)**: {derivative_repo}
**Relationship**: Template Fork - the derivative is based on the template but has diverged

**Template Changes**:
Commit Message: {template_changes.get('commit_message', '')}

Files Changed (filtered to shared concerns):
{json.dumps(files_summary, indent=2)}

Pattern Summary:
{json.dumps(template_changes.get('pattern_summary', {}), indent=2)}

**Matched Shared Concerns**: {relevant_changes['matched_shared_concerns']}
**Matched Divergent Concerns**: {relevant_changes['matched_divergent_concerns']}

**Derivative's Current State** (same files):
{json.dumps(derivative_summary, indent=2)}

**Derivative Configuration**:
- Shared Concerns: {derivative_config.get('shared_concerns', [])}
- Divergent Concerns: {derivative_config.get('divergent_concerns', [])}
- Sync Strategy: {derivative_config.get('sync_strategy', 'selective')}

**Your Task**:
Determine if these template changes should be backported/synced to the derivative.

Consider:
1. **Infrastructure Improvements**: Docker optimizations, deployment improvements, GPU configs
2. **Bug Fixes**: Security patches, critical fixes (should almost always sync)
3. **Configuration Enhancements**: Better health checks, logging, monitoring
4. **Conflicts**: Would these changes conflict with derivative-specific customizations?
5. **Value**: Is there tangible benefit for the derivative?

Guidelines:
- Infrastructure improvements should usually sync
- Bug fixes and security patches are high priority
- Application-specific logic should NOT sync
- Model-specific configurations should NOT sync
- API endpoint changes should NOT sync (divergent concern)

Respond ONLY with valid JSON in this exact format:
{{
  "requires_action": true/false,
  "urgency": "critical|high|medium|low",
  "impact_summary": "Brief 1-2 sentence summary of what changed and why it matters",
  "affected_files": ["file1.yml", "file2.py"],
  "recommended_changes": "Detailed description of what to backport and how",
  "confidence": 0.0-1.0,
  "reasoning": "Explain why this should or should not sync, including any conflict concerns"
}}

**Urgency Levels**:
- critical: Security patch or critical bug fix
- high: Important infrastructure improvement or bug fix
- medium: Nice-to-have optimization or enhancement
- low: Minor improvement or informational

Be selective - only set requires_action=true if the changes genuinely benefit the derivative and don't conflict with its divergent concerns.
"""

        try:
            response = self.anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text
            # Remove markdown code blocks
            import re
            content = re.sub(r'```json\n?|\n?```', '', content).strip()

            result = json.loads(content)

            # Validate
            required_fields = ['requires_action', 'urgency', 'impact_summary', 'confidence', 'reasoning']
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")

            result.setdefault('affected_files', [])
            result.setdefault('recommended_changes', '')

            logger.info(f"Template sync analysis complete: action={result['requires_action']}, urgency={result['urgency']}")

            return result

        except Exception as e:
            logger.error(f"Error in LLM sync analysis: {e}", exc_info=True)
            return {
                'requires_action': False,
                'urgency': 'low',
                'impact_summary': f'Analysis error: {str(e)}',
                'affected_files': [],
                'recommended_changes': '',
                'confidence': 0.0,
                'reasoning': f'Failed to parse LLM response: {str(e)}'
            }
