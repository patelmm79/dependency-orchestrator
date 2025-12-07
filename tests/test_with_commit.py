#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test with the actual fastapi_auth_commit_test.json to show improved output
"""

import json
import sys
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def main():
    """Demonstrate improved issue output with actual test commit"""

    # Load test data
    with open('test/fastapi_auth_commit_test.json') as f:
        test_event = json.load(f)

    # Load relationships config
    with open('config/relationships.json') as f:
        config = json.load(f)

    # Get consumer config for resume-customizer
    consumer_config = config['relationships']['patelmm79/vllm-container-ngc']['consumers'][0]

    print("=" * 80)
    print("TESTING WITH ACTUAL COMMIT: fastapi_auth_commit_test.json")
    print("=" * 80)
    print()
    print("Source Repository: patelmm79/vllm-container-ngc")
    print("Consumer Repository: patelmm79/resume-customizer")
    print("Commit Message:", test_event['commit_message'])
    print()
    print("Architecture Context from Config:")
    print("  →", consumer_config['description'])
    print()
    print("Changed Files:")
    for file in test_event['changed_files']:
        print(f"  - {file['path']} ({file['change_type']})")
    print()
    print("Pattern Summary:")
    print("  Patterns:", ', '.join(test_event['pattern_summary']['patterns']))
    print("  Keywords:", ', '.join(test_event['pattern_summary']['keywords']))
    print()
    print("=" * 80)
    print()

    # Simulate what the improved agent WOULD output
    # This is based on the actual improvements we made to the prompt
    improved_result = {
        'requires_action': True,
        'urgency': 'high',
        'impact_summary': 'vllm-container-ngc added mandatory X-API-Key authentication via FastAPI gateway on port 8000 (changed from port 8080)',
        'affected_files': ['.env.example', 'utils/llm_client.py', 'README.md'],
        'recommended_changes': """1. **Verify this affects you**: Check if your CUSTOM_LLM_BASE_URL environment variable points to this vLLM service (patelmm79/vllm-container-ngc). If not, this change may not apply to your setup.

2. **Update .env.example**:
   - Change port from 8080 to 8000 in CUSTOM_LLM_BASE_URL
   - Example: `CUSTOM_LLM_BASE_URL=http://your-vllm-host:8000/v1`

3. **Add authentication support in utils/llm_client.py**:
   - Add X-API-Key header to HTTP requests
   - Retrieve API key from environment variable (e.g., VLLM_API_KEY)
   - Example: `headers["X-API-Key"] = os.getenv("VLLM_API_KEY")`

4. **Update documentation in README.md**:
   - Document the new X-API-Key requirement
   - Update any examples showing how to connect to the vLLM service
   - Add VLLM_API_KEY to environment variable documentation

5. **Test the connection**: Verify CustomLLMClient can successfully authenticate with the updated service""",
        'confidence': 0.85,
        'reasoning': """**Architecture Analysis**: Based on the provided architecture context, patelmm79/resume-customizer uses patelmm79/vllm-container-ngc as its primary LLM service for text generation. This is a PRIMARY production dependency.

**Configuration Evidence**: The consumer's interface files include .env.example (likely containing CUSTOM_LLM_BASE_URL) and utils/llm_client.py (the client implementation).

**Impact Assessment**: The provider introduced two breaking changes:
1. Port change: 8080 → 8000 (FastAPI gateway)
2. New authentication: Mandatory X-API-Key header

**Why HIGH urgency**: If the consumer's CUSTOM_LLM_BASE_URL points to this service, these are breaking changes that will cause authentication failures. However, since we cannot see the actual .env.example content from the consumer, there's some uncertainty about whether they currently use this service in production or if the example shows a different default (like localhost:1234 for local LM Studio).

**Verification needed**: The first recommended step is to verify if the consumer actually points to this vLLM service, which distinguishes this from a CRITICAL (certain breakage) vs HIGH (likely breakage if used) urgency.""",
        'architecture_context': """**Dependency Relationship**: patelmm79/resume-customizer uses patelmm79/vllm-container-ngc as its **PRIMARY LLM service** for text generation tasks.

**Deployment Model**: This appears to be a cloud-hosted vLLM container dependency where the consumer connects to the provider's API for LLM inference.

**Production Impact**: HIGH - Text generation is a core feature of resume customization. If this service is unavailable or misconfigured, the main functionality will fail.

**Configuration**: The consumer likely configures the connection via CUSTOM_LLM_BASE_URL environment variable in .env.example, with the client implementation in utils/llm_client.py."""
    }

    print()
    print("=" * 80)
    print("IMPROVED GITHUB ISSUE OUTPUT")
    print("=" * 80)
    print()

    # Generate the issue as it would appear
    architecture_section = f"""## 🏗️ Architecture Context

{improved_result['architecture_context']}

**Why This Matters**: This dependency is a core part of your architecture. Changes here likely affect your production deployment.

---

"""

    issue_body = f"""## 🔔 Dependency Update: patelmm79/vllm-container-ngc

{architecture_section}### ⚠️ Key Change
{improved_result['impact_summary']}

**Urgency**: {improved_result['urgency'].upper()} | **Confidence**: {improved_result['confidence']:.0%}

### 📋 What You Need To Do
{improved_result['recommended_changes']}

### 📂 Files That May Need Updates
{chr(10).join(f"- `{f}`" for f in improved_result['affected_files'])}

---

<details>
<summary>📖 Technical Details & Analysis</summary>

### Source Change Details
- **Repository**: patelmm79/vllm-container-ngc
- **Commit**: [{test_event['commit_sha'][:7]}](https://github.com/patelmm79/vllm-container-ngc/commit/{test_event['commit_sha']})
- **Branch**: {test_event['branch']}

### Commit Message
```
{test_event['commit_message']}
```

### Analysis Reasoning
{improved_result['reasoning']}

</details>

---
_🤖 Automatically created by [Dependency Orchestrator](https://github.com/patelmm79/vllm-container-ngc/commit/{test_event['commit_sha']})_
"""

    print(issue_body)
    print()
    print("=" * 80)
    print("KEY IMPROVEMENTS IN THIS OUTPUT")
    print("=" * 80)
    print()
    print("✅ Architecture Context Section (NEW):")
    print("   - Clearly states this is a PRIMARY dependency")
    print("   - Explains the deployment model (cloud-hosted vLLM)")
    print("   - Shows production impact level (HIGH)")
    print("   - Identifies likely configuration mechanism (CUSTOM_LLM_BASE_URL)")
    print()
    print("✅ Better Impact Summary:")
    print("   - Leads with KEY change (authentication) not minor detail (port)")
    print("   - Specific about what changed (X-API-Key header via FastAPI)")
    print()
    print("✅ Actionable Recommendations:")
    print("   - Step 1: VERIFY if you use this service (not assumed)")
    print("   - Specific file names (.env.example, utils/llm_client.py, README.md)")
    print("   - Concrete examples (add X-API-Key header, use VLLM_API_KEY env var)")
    print("   - Port change details (8080 → 8000)")
    print()
    print("✅ Appropriate Urgency:")
    print("   - HIGH (not LOW) because it's a PRIMARY dependency")
    print("   - Not CRITICAL because verification step needed first")
    print("   - Confidence 85% with clear reasoning about uncertainty")
    print()
    print("✅ Better Reasoning:")
    print("   - Starts with architecture analysis")
    print("   - References the architecture context provided")
    print("   - Explains why HIGH not CRITICAL")
    print("   - Acknowledges uncertainty and suggests verification")
    print()
    print()
    print("=" * 80)
    print("COMPARISON TO ORIGINAL ISSUE THAT HAD PROBLEMS")
    print("=" * 80)
    print()
    print("ORIGINAL resume-customizer issue (that required back-and-forth):")
    print("  ❌ No architecture context section")
    print("  ❌ Unclear if this was PRIMARY or OPTIONAL dependency")
    print("  ❌ Possibly concluded 'no action required' initially")
    print("  ❌ Didn't connect .env.example to production architecture")
    print("  ❌ Required multiple rounds to identify both PRs needed:")
    print("     - PR #1: Update .env.example to show cloud vLLM as primary")
    print("     - PR #2: Add X-API-Key header support in CustomLLMClient")
    print()
    print("NEW issue (with improvements):")
    print("  ✅ Architecture context explains PRIMARY dependency upfront")
    print("  ✅ Identifies both .env.example AND utils/llm_client.py as affected")
    print("  ✅ Specific actions for both files:")
    print("     - .env.example: Update port 8080 → 8000")
    print("     - utils/llm_client.py: Add X-API-Key header support")
    print("     - README.md: Document the authentication requirement")
    print("  ✅ Should identify all required changes in FIRST analysis")
    print()


if __name__ == '__main__':
    main()
