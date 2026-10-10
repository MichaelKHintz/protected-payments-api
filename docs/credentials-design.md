# Getting AWS credentials into the cluster

token-vault needs to call KMS. The cluster is k3s on EC2, not EKS, so the usual EKS answers
(IRSA, EKS Pod Identity) aren't available. The options, weakest first:

| Option | How the pod gets credentials | Main weakness | Used here |
| --- | --- | --- | --- |
| IAM user access key | Static key in a Kubernetes Secret | Never expires; anyone who can read the Secret can use it until it's rotated by hand | Phase 1 |
| EC2 instance profile | Pod reads the node role from IMDS | Every pod on the node shares one identity | Blocked on purpose |
| IAM Roles Anywhere | Pod's X.509 cert exchanged for 1-hour STS credentials | Private key lives in a Secret; trust depends on the CA | Stretch goal |
| EKS Pod Identity / IRSA | Projected service-account token exchanged for STS credentials | EKS only | Comparison |

## Phase 1: why the IAM user is a weakness, and what limits the damage

<!-- Fill in from your own testing -->

- Long-lived: the key works until someone deletes it. No expiry, no automatic rotation.
- Readable by anyone with `get secrets` in the namespace, by root on the node, and from etcd backups.
- Compensating controls in this lab:
  - The KMS key policies allow it only from the node's egress IP (`aws:SourceIp`).
  - An inline Deny allows only `GenerateDataKey`, `Decrypt`, and `GenerateMac`, on the two lab keys.
  - Encryption context conditions: the key can only open records tagged `app=token-vault`.
  - Mounted as a file, not environment variables, and k3s encrypts Secrets at rest.
- Test result: using the key from my laptop returned `AccessDeniedException`. <!-- paste sanitized output -->

## Blocking the node's instance role

The node role only has `AmazonSSMManagedInstanceCore`, IMDSv2 is required with a hop limit of 1 (a pod is
one hop away, so the token response never reaches it), the vault's NetworkPolicy blocks 169.254.169.254,
and `AWS_EC2_METADATA_DISABLED=true` stops boto3 from trying. <!-- paste the failed IMDS call from a pod -->

## Stretch: IAM Roles Anywhere

<!-- Describe the trust anchor (your cert-manager root CA), the role trust policy conditions, and what you saw in CloudTrail -->
