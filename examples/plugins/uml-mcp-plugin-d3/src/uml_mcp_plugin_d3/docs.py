"""Where a node's documentation lives: official docs for known services, else a docs search.

A node may set its own ``docs`` (an ``https://`` URL); otherwise the page's detail panel
links here. Every URL is a vendor's own documentation site; nothing is fetched at render
time, the link only opens when a reader clicks it.
"""

from __future__ import annotations

from urllib.parse import quote_plus

#: ``provider:service`` -> documentation home page.
DOCS: dict[str, str] = {
    # ---- AWS
    "aws:ec2": "https://docs.aws.amazon.com/ec2/",
    "aws:lambda": "https://docs.aws.amazon.com/lambda/",
    "aws:ecs": "https://docs.aws.amazon.com/ecs/",
    "aws:eks": "https://docs.aws.amazon.com/eks/",
    "aws:ecr": "https://docs.aws.amazon.com/ecr/",
    "aws:batch": "https://docs.aws.amazon.com/batch/",
    "aws:stepfunctions": "https://docs.aws.amazon.com/step-functions/",
    "aws:cloudformation": "https://docs.aws.amazon.com/cloudformation/",
    "aws:s3": "https://docs.aws.amazon.com/s3/",
    "aws:ebs": "https://docs.aws.amazon.com/ebs/",
    "aws:efs": "https://docs.aws.amazon.com/efs/",
    "aws:rds": "https://docs.aws.amazon.com/rds/",
    "aws:dynamodb": "https://docs.aws.amazon.com/dynamodb/",
    "aws:redshift": "https://docs.aws.amazon.com/redshift/",
    "aws:elasticache": "https://docs.aws.amazon.com/elasticache/",
    "aws:sqs": "https://docs.aws.amazon.com/sqs/",
    "aws:sns": "https://docs.aws.amazon.com/sns/",
    "aws:eventbridge": "https://docs.aws.amazon.com/eventbridge/",
    "aws:kinesis": "https://docs.aws.amazon.com/kinesis/",
    "aws:msk": "https://docs.aws.amazon.com/msk/",
    "aws:ses": "https://docs.aws.amazon.com/ses/",
    "aws:alb": "https://docs.aws.amazon.com/elasticloadbalancing/",
    "aws:nlb": "https://docs.aws.amazon.com/elasticloadbalancing/",
    "aws:elb": "https://docs.aws.amazon.com/elasticloadbalancing/",
    "aws:cloudfront": "https://docs.aws.amazon.com/cloudfront/",
    "aws:apigateway": "https://docs.aws.amazon.com/apigateway/",
    "aws:appsync": "https://docs.aws.amazon.com/appsync/",
    "aws:route53": "https://docs.aws.amazon.com/route53/",
    "aws:vpc": "https://docs.aws.amazon.com/vpc/",
    "aws:waf": "https://docs.aws.amazon.com/waf/",
    "aws:iam": "https://docs.aws.amazon.com/iam/",
    "aws:cognito": "https://docs.aws.amazon.com/cognito/",
    "aws:kms": "https://docs.aws.amazon.com/kms/",
    "aws:secretsmanager": "https://docs.aws.amazon.com/secretsmanager/",
    "aws:guardduty": "https://docs.aws.amazon.com/guardduty/",
    "aws:cloudwatch": "https://docs.aws.amazon.com/cloudwatch/",
    "aws:cloudtrail": "https://docs.aws.amazon.com/cloudtrail/",
    "aws:athena": "https://docs.aws.amazon.com/athena/",
    "aws:glue": "https://docs.aws.amazon.com/glue/",
    "aws:opensearch": "https://docs.aws.amazon.com/opensearch-service/",
    "aws:sagemaker": "https://docs.aws.amazon.com/sagemaker/",
    "aws:bedrock": "https://docs.aws.amazon.com/bedrock/",
    # ---- Azure
    "azure:vm": "https://learn.microsoft.com/azure/virtual-machines/",
    "azure:appservice": "https://learn.microsoft.com/azure/app-service/",
    "azure:functions": "https://learn.microsoft.com/azure/azure-functions/",
    "azure:aks": "https://learn.microsoft.com/azure/aks/",
    "azure:containerapps": "https://learn.microsoft.com/azure/container-apps/",
    "azure:acr": "https://learn.microsoft.com/azure/container-registry/",
    "azure:logicapps": "https://learn.microsoft.com/azure/logic-apps/",
    "azure:datafactory": "https://learn.microsoft.com/azure/data-factory/",
    "azure:blob": "https://learn.microsoft.com/azure/storage/blobs/",
    "azure:storage": "https://learn.microsoft.com/azure/storage/",
    "azure:sql": "https://learn.microsoft.com/azure/azure-sql/",
    "azure:cosmos": "https://learn.microsoft.com/azure/cosmos-db/",
    "azure:postgres": "https://learn.microsoft.com/azure/postgresql/",
    "azure:mysql": "https://learn.microsoft.com/azure/mysql/",
    "azure:redis": "https://learn.microsoft.com/azure/azure-cache-for-redis/",
    "azure:servicebus": "https://learn.microsoft.com/azure/service-bus-messaging/",
    "azure:eventhubs": "https://learn.microsoft.com/azure/event-hubs/",
    "azure:eventgrid": "https://learn.microsoft.com/azure/event-grid/",
    "azure:signalr": "https://learn.microsoft.com/azure/azure-signalr/",
    # ---- Google Cloud
    "gcp:compute": "https://cloud.google.com/compute/docs",
    "gcp:run": "https://cloud.google.com/run/docs",
    "gcp:functions": "https://cloud.google.com/functions/docs",
    "gcp:gke": "https://cloud.google.com/kubernetes-engine/docs",
    "gcp:storage": "https://cloud.google.com/storage/docs",
    "gcp:gcs": "https://cloud.google.com/storage/docs",
    "gcp:sql": "https://cloud.google.com/sql/docs",
    "gcp:cloudsql": "https://cloud.google.com/sql/docs",
    "gcp:spanner": "https://cloud.google.com/spanner/docs",
    "gcp:firestore": "https://cloud.google.com/firestore/docs",
    "gcp:bigquery": "https://cloud.google.com/bigquery/docs",
    "gcp:pubsub": "https://cloud.google.com/pubsub/docs",
    "gcp:memorystore": "https://cloud.google.com/memorystore/docs",
    "gcp:cdn": "https://cloud.google.com/cdn/docs",
    "gcp:loadbalancer": "https://cloud.google.com/load-balancing/docs",
    "gcp:dns": "https://cloud.google.com/dns/docs",
    "gcp:iam": "https://cloud.google.com/iam/docs",
    "gcp:vertexai": "https://cloud.google.com/vertex-ai/docs",
    # ---- Kubernetes
    "kubernetes:pod": "https://kubernetes.io/docs/concepts/workloads/pods/",
    "kubernetes:deployment": "https://kubernetes.io/docs/concepts/workloads/controllers/deployment/",
    "kubernetes:service": "https://kubernetes.io/docs/concepts/services-networking/service/",
    "kubernetes:ingress": "https://kubernetes.io/docs/concepts/services-networking/ingress/",
    "kubernetes:configmap": "https://kubernetes.io/docs/concepts/configuration/configmap/",
    "kubernetes:secret": "https://kubernetes.io/docs/concepts/configuration/secret/",
    "kubernetes:statefulset": "https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/",
    "kubernetes:job": "https://kubernetes.io/docs/concepts/workloads/controllers/job/",
    # ---- software
    "tech:postgres": "https://www.postgresql.org/docs/",
    "tech:mysql": "https://dev.mysql.com/doc/",
    "tech:mariadb": "https://mariadb.com/kb/en/documentation/",
    "tech:mongodb": "https://www.mongodb.com/docs/",
    "tech:sqlite": "https://www.sqlite.org/docs.html",
    "tech:cassandra": "https://cassandra.apache.org/doc/latest/",
    "tech:clickhouse": "https://clickhouse.com/docs",
    "tech:redis": "https://redis.io/docs/",
    "tech:memcached": "https://memcached.org/",
    "tech:elasticsearch": "https://www.elastic.co/docs",
    "tech:kafka": "https://kafka.apache.org/documentation/",
    "tech:rabbitmq": "https://www.rabbitmq.com/docs",
    "tech:nats": "https://docs.nats.io/",
    "tech:nginx": "https://nginx.org/en/docs/",
    "tech:haproxy": "https://docs.haproxy.org/",
    "tech:envoy": "https://www.envoyproxy.io/docs",
    "tech:traefik": "https://doc.traefik.io/traefik/",
    "tech:istio": "https://istio.io/latest/docs/",
    "tech:docker": "https://docs.docker.com/",
    "tech:kubernetes": "https://kubernetes.io/docs/",
    "tech:nodejs": "https://nodejs.org/docs/latest/api/",
    "tech:python": "https://docs.python.org/3/",
    "tech:go": "https://go.dev/doc/",
    "tech:react": "https://react.dev/",
    "tech:vue": "https://vuejs.org/guide/introduction",
    "tech:graphql": "https://graphql.org/learn/",
    "tech:grpc": "https://grpc.io/docs/",
    "tech:prometheus": "https://prometheus.io/docs/",
    "tech:grafana": "https://grafana.com/docs/",
    "tech:jenkins": "https://www.jenkins.io/doc/",
    "tech:github": "https://docs.github.com/",
    "tech:gitlab": "https://docs.gitlab.com/",
    "tech:terraform": "https://developer.hashicorp.com/terraform/docs",
    "tech:ansible": "https://docs.ansible.com/",
    "tech:vault": "https://developer.hashicorp.com/vault/docs",
    "tech:keycloak": "https://www.keycloak.org/documentation",
    "tech:openai": "https://platform.openai.com/docs",
    "tech:anthropic": "https://docs.anthropic.com/",
    "tech:claude": "https://docs.anthropic.com/",
    "tech:vercel": "https://vercel.com/docs",
    "tech:cloudflare": "https://developers.cloudflare.com/",
    "tech:gemini": "https://ai.google.dev/gemini-api/docs",
    "tech:mistral": "https://docs.mistral.ai/",
    "tech:huggingface": "https://huggingface.co/docs",
    "tech:langchain": "https://python.langchain.com/docs/",
    "tech:mcp": "https://modelcontextprotocol.io/",
    "tech:snowflake": "https://docs.snowflake.com/",
    "tech:n8n": "https://docs.n8n.io/",
    "tech:cohere": "https://docs.cohere.com/",
    "tech:vllm": "https://docs.vllm.ai/",
    "tech:llamaindex": "https://docs.llamaindex.ai/",
}

#: A provider's documentation search, for services without a page above.
SEARCH: dict[str, str] = {
    "aws": "https://docs.aws.amazon.com/search/doc-search.html?searchQuery={q}",
    "azure": "https://learn.microsoft.com/search/?terms={q}",
    "gcp": "https://cloud.google.com/s/results?q={q}",
    "kubernetes": "https://kubernetes.io/search/?q={q}",
}

#: Display names the layout carries for software (``PostgreSQL``) -> their ``tech:`` key.
_ALIASES = {
    "postgresql": "postgres",
    "node.js": "nodejs",
    "node": "nodejs",
    "golang": "go",
    "k8s": "kubernetes",
    "elastic": "elasticsearch",
}


def docs_url(service: str | None, provider: str, name: str) -> str | None:
    """The documentation link for a node that names ``service`` (``aws:lambda``,
    ``postgres``...), resolved to ``provider`` and displayed as ``name``."""
    if not service:
        return None
    key = service.strip().lower().partition(":")[2] or service.strip().lower()
    key = _ALIASES.get(key, key)
    for candidate in (f"{provider}:{key}", f"tech:{key}"):
        if candidate in DOCS:
            return DOCS[candidate]
    template = SEARCH.get(provider)
    return template.format(q=quote_plus(name or key)) if template else None
