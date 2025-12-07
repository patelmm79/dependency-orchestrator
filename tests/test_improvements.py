#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to validate improved issue structure with architecture context
"""

import json
import asyncio
import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator.agents.consumer_triage import ConsumerTriageAgent
import anthropic
from github import Github


async def test_consumer_triage():
    """Test the consumer triage agent with FastAPI auth test data"""

    # Load test data
    with open('test/fastapi_auth_commit_test.json') as f:
        test_event = json.load(f)

    # Load relationships config
    with open('config/relationships.json') as f:
        config = json.load(f)

    # Get consumer config for resume-customizer
    consumer_config = None
    for consumer in config['relationships']['patelmm79/vllm-container-ngc']['consumers']:
        if consumer['repo'] == 'patelmm79/resume-customizer':
            consumer_config = consumer
            break

    if not consumer_config:
        print("❌ Could not find resume-customizer consumer config")
        return

    print("🔍 Testing Consumer Triage Agent")
    print("=" * 60)
    print(f"Source: patelmm79/vllm-container-ngc")
    print(f"Consumer: patelmm79/resume-customizer")
    print(f"Architecture Context: {consumer_config.get('description', 'N/A')}")
    print("=" * 60)
    print()

    # Initialize clients
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
    github_token = os.environ.get('GITHUB_TOKEN')

    if not anthropic_key or not github_token:
        print("❌ Missing environment variables:")
        if not anthropic_key:
            print("  - ANTHROPIC_API_KEY")
        if not github_token:
            print("  - GITHUB_TOKEN")
        return

    anthropic_client = anthropic.Anthropic(api_key=anthropic_key)
    github_client = Github(github_token)

    # Initialize agent
    agent = ConsumerTriageAgent(
        anthropic_client=anthropic_client,
        github_client=github_client
    )

    # Run analysis
    print("🤖 Running triage analysis...")
    result = await agent.analyze(
        source_repo='patelmm79/vllm-container-ngc',
        consumer_repo='patelmm79/resume-customizer',
        change_event=test_event,
        consumer_config=consumer_config
    )

    # Display results
    print()
    print("📊 TRIAGE RESULT")
    print("=" * 60)
    print(f"Requires Action: {result['requires_action']}")
    print(f"Urgency: {result['urgency'].upper()}")
    print(f"Confidence: {result['confidence']:.0%}")
    print()

    if result.get('architecture_context'):
        print("🏗️ ARCHITECTURE CONTEXT:")
        print("-" * 60)
        print(result['architecture_context'])
        print()

    print("⚠️ IMPACT SUMMARY:")
    print("-" * 60)
    print(result['impact_summary'])
    print()

    print("📋 RECOMMENDED CHANGES:")
    print("-" * 60)
    print(result['recommended_changes'])
    print()

    if result.get('affected_files'):
        print("📂 AFFECTED FILES:")
        print("-" * 60)
        for file in result['affected_files']:
            print(f"  - {file}")
        print()

    print("💭 REASONING:")
    print("-" * 60)
    print(result['reasoning'])
    print()

    # Show what the issue would look like
    print()
    print("📝 SIMULATED GITHUB ISSUE")
    print("=" * 60)

    architecture_section = ""
    if result.get('architecture_context'):
        architecture_section = f"""## 🏗️ Architecture Context

{result['architecture_context']}

**Why This Matters**: This dependency is a core part of your architecture. Changes here likely affect your production deployment.

---

"""

    issue_body = f"""## 🔔 Dependency Update: patelmm79/vllm-container-ngc

{architecture_section}### ⚠️ Key Change
{result['impact_summary']}

**Urgency**: {result['urgency'].upper()} | **Confidence**: {result['confidence']:.0%}

### 📋 What You Need To Do
{result['recommended_changes']}

### 📂 Files That May Need Updates
{chr(10).join(f"- `{f}`" for f in result['affected_files']) if result['affected_files'] else "_No specific files identified - see verification steps above_"}

---

<details>
<summary>📖 Technical Details & Analysis</summary>

### Source Change Details
- **Repository**: patelmm79/vllm-container-ngc
- **Commit**: [1865d05](https://github.com/patelmm79/vllm-container-ngc/commit/{test_event['commit_sha']})
- **Branch**: main

### Commit Message
```
{test_event['commit_message']}
```

### Analysis Reasoning
{result['reasoning']}

</details>

---
_🤖 Automatically created by [Dependency Orchestrator](https://github.com/patelmm79/vllm-container-ngc/commit/{test_event['commit_sha']})_
"""

    print(issue_body)
    print()
    print("=" * 60)
    print("✅ Test complete!")


if __name__ == '__main__':
    asyncio.run(test_consumer_triage())
