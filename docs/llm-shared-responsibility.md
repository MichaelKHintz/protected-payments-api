# Shared responsibility when sending data to an LLM

<!-- Re-check every cell against the vendor's current page and record the date you checked. -->
As of: <!-- YYYY-MM-DD -->

## What the provider handles vs. what I handle

| | Anthropic API (Claude Platform) | OpenAI API | ChatGPT Enterprise (SaaS) | Amazon Bedrock (Claude via AWS) |
| --- | --- | --- | --- | --- |
| Consumption model | API; my code decides what is sent | API | Managed SaaS app; users type or upload directly | API inside my AWS account boundary |
| Training on my data | | | | |
| Default retention of prompts and outputs | | | | |
| Zero-retention option, and how to get it | | | | |
| Abuse-monitoring or flagged-content retention | | | | |
| Logging I control | My gateway's audit log | My gateway's audit log | Admin console / Compliance API | Model invocation logging to my CloudWatch or S3 (opt-in) |
| Identity and SSO | | | | IAM, Identity Center |
| Access controls | Workspaces, API keys per workspace, spend limits | Projects, project API keys, RBAC | Workspace admin roles, SCIM | IAM policies, SCPs, VPC endpoints |
| Network path | Public internet (TLS) | Public internet (TLS) | Public internet (TLS) | Can stay on AWS PrivateLink |

## My side of the line in this lab

- Decide what leaves: card numbers become vault tokens, PII becomes typed placeholders, and a fail-closed check blocks anything card-shaped.
- Protect the credential: the API key is a Kubernetes Secret mounted as a file, scoped to one Console workspace with a spend limit.
- Keep my own record: every request logs metadata and the redacted prompt, never the raw input.
- Treat the output as untrusted: summaries are scanned for card-shaped numbers before they are returned.

## Sources

<!-- One link per vendor page you used, with the date you read it -->
