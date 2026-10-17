"""Providers, icon glyphs, cloud and software service names, and node categories.

The icons are simple line glyphs drawn for this plugin. They are not the vendors' own
artwork (that carries usage terms), so a diagram reads as AWS, Azure or Google Cloud by its
service name, a small provider badge and its category colour. Popular software (a database,
a broker, a web server) gets a monogram on a brand-coloured tile instead of a glyph. Use
PlantUML's cloud libraries when the official icons are required, or give a node its own
``logo`` as a data URI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .theme import CATEGORIES, CATEGORY_LABELS


@dataclass(frozen=True)
class Provider:
    name: str
    accent: str  # the provider's colour (its badge on a node, the docs table)


PROVIDERS: dict[str, Provider] = {
    "aws": Provider("AWS", "#ED7100"),
    "azure": Provider("Azure", "#0078D4"),
    "gcp": Provider("Google Cloud", "#4285F4"),
    "kubernetes": Provider("Kubernetes", "#326CE5"),
    "onprem": Provider("On premises", "#64748B"),
    "tech": Provider("Software", "#475569"),
    "generic": Provider("Generic", "#475569"),
}

#: 24x24 line glyphs, drawn in the node's category colour.
KINDS: dict[str, str] = {
    "server": (
        '<rect x="3" y="4" width="18" height="6" rx="1.5"/>'
        '<rect x="3" y="14" width="18" height="6" rx="1.5"/><path d="M7 7h.01M7 17h.01"/>'
    ),
    "compute": (
        '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6"/>'
        '<path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>'
    ),
    "function": (
        '<path d="M8 4c-2 0-3 1-3 3v2c0 1-1 2-2 3 1 1 2 2 2 3v2c0 2 1 3 3 3'
        'M16 4c2 0 3 1 3 3v2c0 1 1 2 2 3-1 1-2 2-2 3v2c0 2-1 3-3 3"/>'
    ),
    "container": (
        '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12L4 7.5M12 12v9"/>'
    ),
    "kubernetes": (
        '<path d="M12 3l7.8 4.5v9L12 21l-7.8-4.5v-9z"/><circle cx="12" cy="12" r="2.5"/>'
        '<path d="M12 9.5V6M14.2 13.3l3 1.7M9.8 13.3l-3 1.7"/>'
    ),
    "database": (
        '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6'
        'M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>'
    ),
    "storage": (
        '<path d="M4 7h16l-1.5 12a2 2 0 0 1-2 1.7h-9a2 2 0 0 1-2-1.7z"/>'
        '<ellipse cx="12" cy="7" rx="8" ry="2.5"/>'
    ),
    "queue": '<path d="M3 7h14M3 12h18M3 17h14"/><path d="M18 5l3 2-3 2M18 15l3 2-3 2"/>',
    "topic": (
        '<circle cx="12" cy="12" r="2.5"/><path d="M7.5 7.5a6.4 6.4 0 0 0 0 9M16.5 7.5a6.4 6.4 '
        '0 0 1 0 9M4.5 4.5a10.6 10.6 0 0 0 0 15M19.5 4.5a10.6 10.6 0 0 1 0 15"/>'
    ),
    "stream": '<path d="M3 7c3-3 6 3 9 0s6 3 9 0M3 13c3-3 6 3 9 0s6 3 9 0M3 19c3-3 6 3 9 0s6 3 9 0"/>',
    "cache": '<path d="M13 2L5 13.5h6L10 22l9-12h-6z"/>',
    "loadbalancer": (
        '<circle cx="5" cy="12" r="2"/><path d="M7 12h4M11 12l5-6M11 12h5M11 12l5 6"/>'
        '<circle cx="19" cy="6" r="1.5"/><circle cx="19" cy="12" r="1.5"/>'
        '<circle cx="19" cy="18" r="1.5"/>'
    ),
    "gateway": '<path d="M4 20V10a8 8 0 0 1 16 0v10"/><path d="M4 20h16M9 20v-6h6v6"/>',
    "api": '<path d="M7 8l-4 4 4 4M17 8l4 4-4 4M14 5l-4 14"/>',
    "web": (
        '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M7 6.5h.01M10 6.5h.01"/>'
    ),
    "cdn": (
        '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>'
    ),
    "internet": (
        '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>'
    ),
    "network": (
        '<rect x="3" y="3" width="6" height="6" rx="1"/><rect x="15" y="3" width="6" height="6" rx="1"/>'
        '<rect x="9" y="15" width="6" height="6" rx="1"/><path d="M6 9v3h12V9M12 12v3"/>'
    ),
    "mesh": (
        '<circle cx="6" cy="6" r="2.2"/><circle cx="18" cy="6" r="2.2"/><circle cx="12" cy="18" r="2.2"/>'
        '<path d="M8.2 6h7.6M7 8l4 8M17 8l-4 8"/>'
    ),
    "firewall": (
        '<rect x="3" y="4" width="18" height="16" rx="1"/>'
        '<path d="M3 9.3h18M3 14.6h18M9 4v5.3M15 9.3v5.3M9 14.6V20"/>'
    ),
    "dns": (
        '<circle cx="12" cy="12" r="3.2"/><path d="M15.2 12v1.5a2.4 2.4 0 0 0 4.8 0V12a8 8 0 1 0-3.2 6.4"/>'
    ),
    "identity": '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3M14 9l2 2"/>',
    "secret": (
        '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9.5 12l2 2 3.5-4"/>'
    ),
    "lock": (
        '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3M12 15v2.5"/>'
    ),
    "monitoring": '<path d="M3 3v18h18"/><path d="M7 15l4-5 3 3 5-7"/>',
    "analytics": '<path d="M5 20V10M12 20V4M19 20v-7"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L21 21"/>',
    "ai": (
        '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/>'
        '<path d="M18 15l.8 2.2L21 18l-2.2.8L18 21l-.8-2.2L15 18l2.2-.8z"/>'
    ),
    "workflow": (
        '<rect x="3" y="3" width="6" height="6" rx="1"/><rect x="15" y="15" width="6" height="6" rx="1"/>'
        '<path d="M9 6h4a2 2 0 0 1 2 2v7"/>'
    ),
    "batch": '<path d="M12 3l9 4.5-9 4.5-9-4.5z"/><path d="M3 12l9 4.5 9-4.5M3 16.5L12 21l9-4.5"/>',
    "registry": '<path d="M4 8l8-5 8 5v8l-8 5-8-5z"/><path d="M4 8l8 5 8-5M12 13v8"/>',
    "backup": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 8v5l3 2"/>',
    "ci": (
        '<path d="M4 12a8 8 0 0 1 14-5.3L20 9M20 4v5h-5M20 12a8 8 0 0 1-14 5.3L4 15M4 20v-5h5"/>'
    ),
    "git": (
        '<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="9" r="2"/>'
        '<path d="M6 7v10M18 11a6 6 0 0 1-6 6H6"/>'
    ),
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
    "document": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
    "iot": (
        '<circle cx="12" cy="18" r="1.5"/><path d="M8.5 14.5a5 5 0 0 1 7 0M5.5 11.5a9 9 0 0 1 13 0'
        'M2.5 8.5a13 13 0 0 1 19 0"/>'
    ),
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "device": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    "mobile": '<rect x="7" y="2.5" width="10" height="19" rx="2"/><path d="M11 18.5h2"/>',
    "cloud": '<path d="M7 18a4.5 4.5 0 0 1-.5-9A6 6 0 0 1 18 9.5 4 4 0 0 1 17 18z"/>',
    "service": (
        '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1'
        'M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>'
    ),
}

#: Which of the seven categories (see ``theme``) a kind of node belongs to.
KIND_CATEGORY: dict[str, str] = {
    "user": "external",
    "mobile": "external",
    "device": "external",
    "internet": "external",
    "iot": "external",
    "gateway": "frontend",
    "cdn": "frontend",
    "loadbalancer": "frontend",
    "dns": "frontend",
    "web": "frontend",
    "server": "backend",
    "compute": "backend",
    "function": "backend",
    "container": "backend",
    "kubernetes": "backend",
    "service": "backend",
    "api": "backend",
    "workflow": "backend",
    "batch": "backend",
    "ai": "backend",
    "mesh": "backend",
    "database": "database",
    "cache": "database",
    "analytics": "database",
    "search": "database",
    "storage": "database",
    "backup": "database",
    "document": "database",
    "network": "cloud",
    "cloud": "cloud",
    "monitoring": "cloud",
    "registry": "cloud",
    "ci": "cloud",
    "git": "cloud",
    "firewall": "security",
    "identity": "security",
    "secret": "security",
    "lock": "security",
    "queue": "messagebus",
    "topic": "messagebus",
    "stream": "messagebus",
    "mail": "messagebus",
}

# provider:service -> (kind, display name)
SERVICES: dict[str, tuple[str, str]] = {
    # AWS
    "aws:ec2": ("server", "EC2"),
    "aws:lightsail": ("server", "Lightsail"),
    "aws:lambda": ("function", "Lambda"),
    "aws:ecs": ("container", "ECS"),
    "aws:fargate": ("container", "Fargate"),
    "aws:eks": ("kubernetes", "EKS"),
    "aws:ecr": ("registry", "ECR"),
    "aws:batch": ("batch", "Batch"),
    "aws:stepfunctions": ("workflow", "Step Functions"),
    "aws:cloudformation": ("workflow", "CloudFormation"),
    "aws:s3": ("storage", "S3"),
    "aws:ebs": ("storage", "EBS"),
    "aws:efs": ("storage", "EFS"),
    "aws:backup": ("backup", "Backup"),
    "aws:rds": ("database", "RDS"),
    "aws:aurora": ("database", "Aurora"),
    "aws:dynamodb": ("database", "DynamoDB"),
    "aws:documentdb": ("database", "DocumentDB"),
    "aws:neptune": ("database", "Neptune"),
    "aws:redshift": ("analytics", "Redshift"),
    "aws:elasticache": ("cache", "ElastiCache"),
    "aws:sqs": ("queue", "SQS"),
    "aws:mq": ("queue", "Amazon MQ"),
    "aws:sns": ("topic", "SNS"),
    "aws:eventbridge": ("topic", "EventBridge"),
    "aws:kinesis": ("stream", "Kinesis"),
    "aws:msk": ("stream", "MSK"),
    "aws:ses": ("mail", "SES"),
    "aws:alb": ("loadbalancer", "ALB"),
    "aws:nlb": ("loadbalancer", "NLB"),
    "aws:elb": ("loadbalancer", "ELB"),
    "aws:cloudfront": ("cdn", "CloudFront"),
    "aws:apigateway": ("gateway", "API Gateway"),
    "aws:appsync": ("api", "AppSync"),
    "aws:route53": ("dns", "Route 53"),
    "aws:vpc": ("network", "VPC"),
    "aws:transitgateway": ("network", "Transit Gateway"),
    "aws:directconnect": ("network", "Direct Connect"),
    "aws:appmesh": ("mesh", "App Mesh"),
    "aws:waf": ("firewall", "WAF"),
    "aws:shield": ("firewall", "Shield"),
    "aws:iam": ("identity", "IAM"),
    "aws:cognito": ("identity", "Cognito"),
    "aws:kms": ("secret", "KMS"),
    "aws:secretsmanager": ("secret", "Secrets Manager"),
    "aws:guardduty": ("secret", "GuardDuty"),
    "aws:cloudwatch": ("monitoring", "CloudWatch"),
    "aws:cloudtrail": ("monitoring", "CloudTrail"),
    "aws:codepipeline": ("ci", "CodePipeline"),
    "aws:codebuild": ("ci", "CodeBuild"),
    "aws:codecommit": ("git", "CodeCommit"),
    "aws:athena": ("analytics", "Athena"),
    "aws:glue": ("analytics", "Glue"),
    "aws:opensearch": ("search", "OpenSearch"),
    "aws:sagemaker": ("ai", "SageMaker"),
    "aws:bedrock": ("ai", "Bedrock"),
    "aws:iotcore": ("iot", "IoT Core"),
    # Azure
    "azure:vm": ("server", "Virtual Machine"),
    "azure:appservice": ("compute", "App Service"),
    "azure:functions": ("function", "Functions"),
    "azure:aks": ("kubernetes", "AKS"),
    "azure:containerapps": ("container", "Container Apps"),
    "azure:aci": ("container", "Container Instances"),
    "azure:servicefabric": ("container", "Service Fabric"),
    "azure:acr": ("registry", "Container Registry"),
    "azure:batch": ("batch", "Batch"),
    "azure:logicapps": ("workflow", "Logic Apps"),
    "azure:datafactory": ("workflow", "Data Factory"),
    "azure:blob": ("storage", "Blob Storage"),
    "azure:storage": ("storage", "Storage"),
    "azure:backup": ("backup", "Backup"),
    "azure:sql": ("database", "SQL Database"),
    "azure:cosmos": ("database", "Cosmos DB"),
    "azure:postgres": ("database", "PostgreSQL"),
    "azure:mysql": ("database", "MySQL"),
    "azure:redis": ("cache", "Cache for Redis"),
    "azure:servicebus": ("queue", "Service Bus"),
    "azure:eventhubs": ("stream", "Event Hubs"),
    "azure:eventgrid": ("topic", "Event Grid"),
    "azure:signalr": ("stream", "SignalR"),
    "azure:communication": ("mail", "Communication Services"),
    "azure:loadbalancer": ("loadbalancer", "Load Balancer"),
    "azure:appgw": ("loadbalancer", "Application Gateway"),
    "azure:frontdoor": ("cdn", "Front Door"),
    "azure:cdn": ("cdn", "CDN"),
    "azure:apim": ("gateway", "API Management"),
    "azure:dns": ("dns", "DNS"),
    "azure:vnet": ("network", "Virtual Network"),
    "azure:expressroute": ("network", "ExpressRoute"),
    "azure:privatelink": ("network", "Private Link"),
    "azure:firewall": ("firewall", "Firewall"),
    "azure:ddos": ("firewall", "DDoS Protection"),
    "azure:entra": ("identity", "Entra ID"),
    "azure:keyvault": ("secret", "Key Vault"),
    "azure:sentinel": ("secret", "Sentinel"),
    "azure:monitor": ("monitoring", "Monitor"),
    "azure:devops": ("ci", "DevOps"),
    "azure:repos": ("git", "Repos"),
    "azure:synapse": ("analytics", "Synapse"),
    "azure:databricks": ("analytics", "Databricks"),
    "azure:search": ("search", "AI Search"),
    "azure:openai": ("ai", "OpenAI Service"),
    "azure:iothub": ("iot", "IoT Hub"),
    # Google Cloud
    "gcp:compute": ("server", "Compute Engine"),
    "gcp:gce": ("server", "Compute Engine"),
    "gcp:appengine": ("compute", "App Engine"),
    "gcp:functions": ("function", "Cloud Functions"),
    "gcp:run": ("container", "Cloud Run"),
    "gcp:gke": ("kubernetes", "GKE"),
    "gcp:artifactregistry": ("registry", "Artifact Registry"),
    "gcp:workflows": ("workflow", "Workflows"),
    "gcp:composer": ("workflow", "Composer"),
    "gcp:scheduler": ("workflow", "Cloud Scheduler"),
    "gcp:storage": ("storage", "Cloud Storage"),
    "gcp:gcs": ("storage", "Cloud Storage"),
    "gcp:sql": ("database", "Cloud SQL"),
    "gcp:spanner": ("database", "Spanner"),
    "gcp:bigtable": ("database", "Bigtable"),
    "gcp:firestore": ("database", "Firestore"),
    "gcp:memorystore": ("cache", "Memorystore"),
    "gcp:pubsub": ("topic", "Pub/Sub"),
    "gcp:tasks": ("queue", "Cloud Tasks"),
    "gcp:datastream": ("stream", "Datastream"),
    "gcp:loadbalancing": ("loadbalancer", "Load Balancing"),
    "gcp:cdn": ("cdn", "Cloud CDN"),
    "gcp:apigee": ("gateway", "Apigee"),
    "gcp:dns": ("dns", "Cloud DNS"),
    "gcp:vpc": ("network", "VPC"),
    "gcp:nat": ("network", "Cloud NAT"),
    "gcp:interconnect": ("network", "Interconnect"),
    "gcp:armor": ("firewall", "Cloud Armor"),
    "gcp:iam": ("identity", "IAM"),
    "gcp:kms": ("secret", "Cloud KMS"),
    "gcp:secretmanager": ("secret", "Secret Manager"),
    "gcp:monitoring": ("monitoring", "Cloud Monitoring"),
    "gcp:logging": ("monitoring", "Cloud Logging"),
    "gcp:cloudbuild": ("ci", "Cloud Build"),
    "gcp:sourcerepos": ("git", "Source Repositories"),
    "gcp:bigquery": ("analytics", "BigQuery"),
    "gcp:dataflow": ("analytics", "Dataflow"),
    "gcp:dataproc": ("analytics", "Dataproc"),
    "gcp:looker": ("analytics", "Looker"),
    "gcp:vertexai": ("ai", "Vertex AI"),
    # Kubernetes
    "kubernetes:cluster": ("kubernetes", "Cluster"),
    "kubernetes:node": ("server", "Node"),
    "kubernetes:pod": ("container", "Pod"),
    "kubernetes:deployment": ("container", "Deployment"),
    "kubernetes:statefulset": ("container", "StatefulSet"),
    "kubernetes:daemonset": ("container", "DaemonSet"),
    "kubernetes:job": ("batch", "Job"),
    "kubernetes:cronjob": ("batch", "CronJob"),
    "kubernetes:hpa": ("compute", "HPA"),
    "kubernetes:service": ("loadbalancer", "Service"),
    "kubernetes:ingress": ("gateway", "Ingress"),
    "kubernetes:networkpolicy": ("firewall", "NetworkPolicy"),
    "kubernetes:configmap": ("document", "ConfigMap"),
    "kubernetes:pvc": ("storage", "PVC"),
    "kubernetes:pv": ("storage", "PV"),
    "kubernetes:secret": ("secret", "Secret"),
    "kubernetes:serviceaccount": ("identity", "ServiceAccount"),
    # On premises
    "onprem:server": ("server", "Server"),
    "onprem:vm": ("server", "Virtual machine"),
    "onprem:hypervisor": ("server", "Hypervisor"),
    "onprem:mainframe": ("server", "Mainframe"),
    "onprem:database": ("database", "Database"),
    "onprem:firewall": ("firewall", "Firewall"),
    "onprem:vpn": ("lock", "VPN"),
    "onprem:loadbalancer": ("loadbalancer", "Load balancer"),
    "onprem:switch": ("network", "Switch"),
    "onprem:router": ("network", "Router"),
    "onprem:storage": ("storage", "Storage"),
    "onprem:nas": ("storage", "NAS"),
    "onprem:san": ("storage", "SAN"),
    "onprem:workstation": ("device", "Workstation"),
    # Popular software: drawn as a monogram on a brand-coloured tile
    "tech:postgres": ("database", "PostgreSQL"),
    "tech:mysql": ("database", "MySQL"),
    "tech:mariadb": ("database", "MariaDB"),
    "tech:mongodb": ("database", "MongoDB"),
    "tech:sqlite": ("database", "SQLite"),
    "tech:cassandra": ("database", "Cassandra"),
    "tech:clickhouse": ("analytics", "ClickHouse"),
    "tech:redis": ("cache", "Redis"),
    "tech:memcached": ("cache", "Memcached"),
    "tech:elasticsearch": ("search", "Elasticsearch"),
    "tech:kafka": ("stream", "Kafka"),
    "tech:rabbitmq": ("queue", "RabbitMQ"),
    "tech:nats": ("queue", "NATS"),
    "tech:nginx": ("gateway", "NGINX"),
    "tech:haproxy": ("loadbalancer", "HAProxy"),
    "tech:envoy": ("mesh", "Envoy"),
    "tech:traefik": ("gateway", "Traefik"),
    "tech:istio": ("mesh", "Istio"),
    "tech:docker": ("container", "Docker"),
    "tech:kubernetes": ("kubernetes", "Kubernetes"),
    "tech:nodejs": ("server", "Node.js"),
    "tech:python": ("server", "Python"),
    "tech:java": ("server", "Java"),
    "tech:go": ("server", "Go"),
    "tech:react": ("web", "React"),
    "tech:vue": ("web", "Vue"),
    "tech:graphql": ("api", "GraphQL"),
    "tech:grpc": ("api", "gRPC"),
    "tech:prometheus": ("monitoring", "Prometheus"),
    "tech:grafana": ("monitoring", "Grafana"),
    "tech:jenkins": ("ci", "Jenkins"),
    "tech:github": ("git", "GitHub"),
    "tech:gitlab": ("git", "GitLab"),
    "tech:terraform": ("workflow", "Terraform"),
    "tech:ansible": ("workflow", "Ansible"),
    "tech:vault": ("secret", "Vault"),
    "tech:keycloak": ("identity", "Keycloak"),
}

#: Software services: (monogram, tile colour). White text sits on every tile.
BRANDS: dict[str, tuple[str, str]] = {
    "postgres": ("Pg", "#336791"),
    "mysql": ("My", "#00758F"),
    "mariadb": ("Ma", "#003545"),
    "mongodb": ("Mo", "#3F8F3F"),
    "sqlite": ("Sq", "#0F6FA8"),
    "cassandra": ("Ca", "#1287B1"),
    "clickhouse": ("Ch", "#B58900"),
    "redis": ("Rd", "#D82C20"),
    "memcached": ("Mc", "#3D6B8F"),
    "elasticsearch": ("Es", "#0B7D8C"),
    "kafka": ("Kf", "#3A3A3A"),
    "rabbitmq": ("Rb", "#E85D04"),
    "nats": ("Nt", "#27AAE1"),
    "nginx": ("Nx", "#009639"),
    "haproxy": ("Hp", "#2C5F8A"),
    "envoy": ("En", "#AC6199"),
    "traefik": ("Tr", "#1A8FA6"),
    "istio": ("Is", "#466BB0"),
    "docker": ("Dk", "#2496ED"),
    "kubernetes": ("K8", "#326CE5"),
    "nodejs": ("Nd", "#3C873A"),
    "python": ("Py", "#3776AB"),
    "java": ("Jv", "#C45A00"),
    "go": ("Go", "#00A7C7"),
    "react": ("Re", "#0E7490"),
    "vue": ("Vu", "#35A474"),
    "graphql": ("Gq", "#C2185B"),
    "grpc": ("gR", "#2A8F8F"),
    "prometheus": ("Pm", "#E6522C"),
    "grafana": ("Gf", "#E05A00"),
    "jenkins": ("Jk", "#C0392B"),
    "github": ("Gh", "#24292F"),
    "gitlab": ("Gl", "#E24329"),
    "terraform": ("Tf", "#7B42BC"),
    "ansible": ("An", "#C00000"),
    "vault": ("Vt", "#B7791F"),
    "keycloak": ("Kc", "#4D4D4D"),
}


@dataclass(frozen=True)
class Resolved:
    provider: str
    kind: str
    name: str
    mono: str | None = None  # monogram of a software service
    color: str | None = None  # its tile colour

    @property
    def category(self) -> str:
        return KIND_CATEGORY.get(self.kind, "backend")


def _title(key: str) -> str:
    return key.replace("_", " ").replace("-", " ").title()


def resolve_service(
    service: str | None, kind: str | None, default_provider: str
) -> Resolved:
    """Work out a node's provider, glyph kind, display name and monogram.

    ``service`` is ``"aws:s3"`` (provider prefix) or just ``"s3"`` (the diagram's
    ``provider`` is used), or a bare kind such as ``"database"``. A bare software name such
    as ``"postgres"`` works under any provider. An explicit ``kind`` always picks the glyph.
    Unknown services still render, with a generic gear.
    """
    provider = default_provider if default_provider in PROVIDERS else "generic"
    key = ""
    explicit = False  # the service named its provider (``aws:s3``)
    if service:
        prefix, sep, rest = service.strip().lower().partition(":")
        if sep and prefix in PROVIDERS:
            provider, key, explicit = prefix, rest, True
        elif sep:
            key = rest  # unknown prefix: validation reports it, rendering stays generic
        else:
            key = prefix
    known = SERVICES.get(f"{provider}:{key}") if key else None
    if (
        known is None
        and key
        and not explicit
        and key not in KINDS
        and f"tech:{key}" in SERVICES
    ):
        provider, known = "tech", SERVICES[f"tech:{key}"]
    brand = BRANDS.get(key) if provider == "tech" else None
    mono, color = brand if brand else (None, None)
    if kind:
        name = known[1] if known else (_title(key) if key else _title(kind))
        return Resolved(provider, kind, name, mono, color)
    if known:
        return Resolved(provider, known[0], known[1], mono, color)
    if key in KINDS:
        return Resolved(provider, key, _title(key))
    return Resolved(provider, "service", _title(key) if key else "Service")


def catalog(provider: str | None = None) -> dict[str, Any]:
    """What a model can use: providers, services (``provider:service``), kinds, categories."""
    services: dict[str, str] = {}
    for key, (kind, name) in sorted(SERVICES.items()):
        if provider and not key.startswith(f"{provider}:"):
            continue
        services[key] = f"{name} ({kind})"
    return {
        "providers": {key: value.name for key, value in PROVIDERS.items()},
        "services": services,
        "kinds": sorted(KINDS),
        "categories": {name: CATEGORY_LABELS[name] for name in CATEGORIES},
    }
