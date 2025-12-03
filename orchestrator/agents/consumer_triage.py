#!/usr/bin/env python3
"""
Consumer Triage Agent - Analyzes impact of API changes on consumer applications
"""

import json
import logging
from typing import Dict, List
import anthropic
from github import Github

logger = logging.getLogger(__name__)


class ConsumerTriageAgent:
    """
    Analyzes changes in a service provider and determines impact on API consumers.

    Use Case: vllm-container-ngc changes → impact on resume-customizer
    """

    def __init__(self, anthropic_client: anthropic.Anthropic, github_client: Github):
        self.anthropic = anthropic_client
        self.github = github_client

    async def analyze(
        self,
        source_repo: str,
        consumer_repo: str,
        change_event: Dict,
        consumer_config: Dict
    ) -> Dict:
        """
        Analyze if changes in source repo require action in consumer repo.

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
            logger.info(f"Analyzing consumer impact: {source_repo} -> {consumer_repo}")

            # 1. Fetch consumer repository code (interface files)
            consumer_code = await self._fetch_consumer_interface_code(
                consumer_repo,
                consumer_config.get('interface_files', [])
            )

            # 2. Extract relevant changes from source
            relevant_changes = self._filter_relevant_changes(
                change_event,
                consumer_config.get('change_triggers', [])
            )

            if not relevant_changes['is_relevant']:
                return {
                    'requires_action': False,
                    'urgency': 'low',
                    'impact_summary': 'No changes affecting consumer API contract',
                    'affected_files': [],
                    'recommended_changes': '',
                    'confidence': 0.9,
                    'reasoning': 'Changes do not match configured trigger patterns'
                }

            # 3. Use LLM to analyze impact
            analysis = await self._llm_analyze_impact(
                source_repo=source_repo,
                consumer_repo=consumer_repo,
                source_changes=change_event,
                consumer_code=consumer_code,
                consumer_config=consumer_config
            )

            return analysis

        except Exception as e:
            logger.error(f"Error in consumer triage analysis: {e}", exc_info=True)
            return {
                'requires_action': False,
                'urgency': 'low',
                'impact_summary': f'Error during analysis: {str(e)}',
                'affected_files': [],
                'recommended_changes': '',
                'confidence': 0.0,
                'reasoning': f'Analysis failed: {str(e)}'
            }

    async def _fetch_consumer_interface_code(self, consumer_repo: str, interface_files: List[str]) -> Dict:
        """Fetch the consumer's interface code (how it interacts with the provider)"""
        code_context = {}

        try:
            repo = self.github.get_repo(consumer_repo)

            for file_path in interface_files[:5]:  # Limit to avoid too much context
                try:
                    content = repo.get_contents(file_path)
                    if content.size < 100000:  # Skip very large files
                        code_context[file_path] = content.decoded_content.decode('utf-8')
                except Exception as e:
                    logger.warning(f"Could not fetch {file_path}: {e}")
                    code_context[file_path] = f"<file not found or inaccessible: {e}>"

        except Exception as e:
            logger.error(f"Error fetching consumer code: {e}")

        return code_context

    def _filter_relevant_changes(self, change_event: Dict, change_triggers: List[str]) -> Dict:
        """
        Filter changes to only those matching configured triggers.

        Triggers: api_contract, authentication, deployment, configuration, endpoints
        """
        changed_files = change_event.get('changed_files', [])
        pattern_summary = change_event.get('pattern_summary', {})

        # Check if patterns match triggers
        patterns = pattern_summary.get('patterns', [])
        keywords = pattern_summary.get('keywords', [])

        # Map patterns/keywords to triggers
        trigger_matches = []

        for trigger in change_triggers:
            if trigger == 'api_contract':
                if any(kw in str(patterns + keywords).lower() for kw in ['api', 'endpoint', 'route', 'contract', 'schema', 'interface']):
                    trigger_matches.append(trigger)
            elif trigger == 'authentication':
                if any(kw in str(patterns + keywords).lower() for kw in ['auth', 'token', 'credential', 'security', 'login']):
                    trigger_matches.append(trigger)
            elif trigger == 'deployment':
                if any(kw in str(patterns + keywords).lower() for kw in ['docker', 'deploy', 'port', 'host', 'url', 'environment']):
                    trigger_matches.append(trigger)
            elif trigger == 'configuration':
                if any(kw in str(patterns + keywords).lower() for kw in ['config', 'setting', 'env', 'parameter']):
                    trigger_matches.append(trigger)
            elif trigger == 'endpoints':
                if any(kw in str(patterns + keywords).lower() for kw in ['endpoint', 'route', 'path', 'url', 'api']):
                    trigger_matches.append(trigger)

        # Also check file paths
        api_file_patterns = ['api', 'route', 'endpoint', 'controller', 'server', 'app.py', 'main.py', 'config']
        file_matches = [f for f in changed_files if any(pattern in f.get('path', '').lower() for pattern in api_file_patterns)]

        is_relevant = len(trigger_matches) > 0 or len(file_matches) > 0

        return {
            'is_relevant': is_relevant,
            'trigger_matches': trigger_matches,
            'relevant_files': file_matches
        }

    async def _llm_analyze_impact(
        self,
        source_repo: str,
        consumer_repo: str,
        source_changes: Dict,
        consumer_code: Dict,
        consumer_config: Dict
    ) -> Dict:
        """Use Claude to analyze the actual impact on the consumer"""

        # Prepare change summary
        changed_files = source_changes.get('changed_files', [])
        files_summary = []
        for file in changed_files[:10]:
            files_summary.append({
                'path': file.get('path', ''),
                'change_type': file.get('change_type', ''),
                'diff': file.get('diff', '')[:1500]  # Truncate
            })

        # Prepare consumer code summary
        consumer_summary = {}
        for path, code in consumer_code.items():
            consumer_summary[path] = code[:2000]  # Truncate

        prompt = f"""You are analyzing the impact of changes in a service provider repository on a consumer application.

**Provider Repository (Source)**: {source_repo}
**Consumer Repository (Target)**: {consumer_repo}
**Relationship**: API Consumer - the consumer depends on the provider's API/service

**Provider Changes**:
Commit Message: {source_changes.get('commit_message', '')}

Files Changed:
{json.dumps(files_summary, indent=2)}

Pattern Summary:
{json.dumps(source_changes.get('pattern_summary', {}), indent=2)}

**Consumer Code Context** (how consumer currently uses the provider):
{json.dumps(consumer_summary, indent=2)}

**Consumer Configuration**:
- Interface Files: {consumer_config.get('interface_files', [])}
- Change Triggers: {consumer_config.get('change_triggers', [])}

**Your Task**:
Analyze whether these changes in the provider require action in the consumer repository.

Consider:
1. **Breaking Changes**: Did the API contract change? Endpoints, authentication, request/response formats?
2. **Configuration Changes**: Do environment variables, ports, URLs, or deployment configs need updating?
3. **Authentication/Security**: Did auth mechanisms change?
4. **Deployment Changes**: Does the consumer need to update how it connects (ports, URLs, Docker configs)?
5. **Non-Breaking Improvements**: Are there optional improvements the consumer should consider?

Respond ONLY with valid JSON in this exact format:
{{
  "requires_action": true/false,
  "urgency": "critical|high|medium|low",
  "impact_summary": "Brief 1-2 sentence summary of impact",
  "affected_files": ["file1.py", "file2.yaml"],
  "recommended_changes": "Detailed description of what needs to change in the consumer",
  "confidence": 0.0-1.0,
  "reasoning": "Explain your analysis and why you reached this conclusion"
}}

**Urgency Levels**:
- critical: Breaking change that will cause immediate failures
- high: Breaking change that will cause issues soon
- medium: Non-breaking but important update needed
- low: Optional improvement or informational

Be conservative - only set requires_action=true if there's a genuine need for the consumer to take action.
"""

        try:
            response = self.anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text
            # Remove markdown code blocks if present
            import re
            content = re.sub(r'```json\n?|\n?```', '', content).strip()

            result = json.loads(content)

            # Validate required fields
            required_fields = ['requires_action', 'urgency', 'impact_summary', 'confidence', 'reasoning']
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")

            # Set defaults for optional fields
            result.setdefault('affected_files', [])
            result.setdefault('recommended_changes', '')

            logger.info(f"LLM analysis complete: action={result['requires_action']}, urgency={result['urgency']}")

            return result

        except Exception as e:
            logger.error(f"Error in LLM analysis: {e}", exc_info=True)
            return {
                'requires_action': False,
                'urgency': 'low',
                'impact_summary': f'Analysis error: {str(e)}',
                'affected_files': [],
                'recommended_changes': '',
                'confidence': 0.0,
                'reasoning': f'Failed to parse LLM response: {str(e)}'
            }
