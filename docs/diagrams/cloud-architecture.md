---
title: Cloud architecture diagrams
description: Draw AWS, Azure, Google Cloud and Kubernetes architectures with official icons (PlantUML libraries) or interactive diagrams (D3 plugin), and deployment views with C4.
tags:
  - reference
  - diagrams
---

# Cloud architecture diagrams

There are three good ways to draw a cloud architecture with UML-MCP. Pick by what you need:

| You need | Use | `diagram_type` | Output |
| --- | --- | --- | --- |
| **Official** AWS, Azure or Google Cloud icons | PlantUML icon libraries (below) | `plantuml` | `svg`, `png`, `pdf` |
| A deployment view: nodes, containers, databases | C4 deployment (below) | `plantuml` | `svg`, `png`, `pdf` |
| An **interactive** diagram: zoom, pan, drag boxes, nested groups, named input and output ports | The [D3 plugin](../plugins/d3.md) | `d3_architecture`, `d3_topology` | `html`, `svg` |

The PlantUML libraries are bundled with PlantUML, so the `<...>` includes resolve when Kroki
renders and these diagrams need no extra setup beyond a Kroki server. Send the source with
`generate_uml` and `diagram_type: plantuml`.

!!! warning "Include names must be exact"

    A wrong include name is the usual failure, and it is reported as
    `cannot include <gcp/Compute/ComputeEngine>`. The examples on this page all render; the macro
    names follow the include file names, so Google Cloud uses `Compute_Engine`, not
    `ComputeEngine`. Not every service has an include, so when Kroki reports
    `cannot include <...>`, check the file name.

## AWS

```plantuml
@startuml
!include <awslib/AWSCommon>
!include <awslib/Compute/EC2>
!include <awslib/Database/RDS>
!include <awslib/Storage/SimpleStorageService>

EC2(web, "Web", "t3.micro")
RDS(db, "Orders", "PostgreSQL")
SimpleStorageService(assets, "Assets", "bucket")
web --> db
web --> assets
@enduml
```

Each service is one include and one macro: `!include <awslib/Compute/Lambda>` gives `Lambda(...)`, and
`!include <awslib/NetworkingContentDelivery/ElasticLoadBalancing>` gives `ElasticLoadBalancing(...)`.
The macro takes an alias, a label and a description.

## Azure

```plantuml
@startuml
!include <azure/AzureCommon>
!include <azure/Compute/AzureVirtualMachine>
!include <azure/Databases/AzureSqlDatabase>

AzureVirtualMachine(vm, "Web", "B2s")
AzureSqlDatabase(db, "Orders", "S1")
vm --> db
@enduml
```

## Google Cloud

```plantuml
@startuml
!include <gcp/GCPCommon>
!include <gcp/Compute/Cloud_Run>
!include <gcp/Databases/Cloud_SQL>
!include <gcp/Storage/Cloud_Storage>

Cloud_Run(api, "API", "python")
Cloud_SQL(db, "Orders", "PostgreSQL")
Cloud_Storage(files, "Assets", "bucket")
api --> db
api --> files
@enduml
```

Other includes that exist: `gcp/Compute/Compute_Engine`, `gcp/Compute/Kubernetes_Engine`,
`gcp/Compute/Cloud_Functions` and `gcp/Networking/Cloud_Load_Balancing`.

## Kubernetes

```plantuml
@startuml
!include <kubernetes/k8s-sprites-unlabeled-25pct>

rectangle "<$pod>\nweb" as p1
rectangle "<$svc>\nservice" as s1
s1 --> p1
@enduml
```

## Deployment view with C4

```plantuml
@startuml
!include <C4/C4_Deployment>

Deployment_Node(dc, "Region", "eu-west-1") {
  Deployment_Node(vm, "EC2", "t3.micro") {
    Container(api, "API", "Python", "serves requests")
  }
  ContainerDb(db, "Orders", "PostgreSQL", "stores orders")
}
Rel(api, db, "reads and writes")
@enduml
```

C4 draws boxes and labels, not vendor icons. See [C4 (PlantUML)](c4plantuml.md) for the rest of
the C4 macros.

## Interactive diagrams

For a diagram you can explore, use the [D3 plugin](../plugins/d3.md). It draws the same kinds of
architecture, with nested groups (region, VPC, subnet), named ports and arrows routed around the
boxes, and renders to an HTML page or an SVG with no Kroki call:

```json
{
  "provider": "aws",
  "nodes": [
    {"id": "web", "service": "aws:ec2"},
    {"id": "db", "service": "aws:rds"}
  ],
  "links": [{"from": "web", "to": "db"}]
}
```

Its icons are original glyphs in the colour of each node's category, with a provider badge, a
monogram tile for popular software (`postgres`, `kafka`, `redis` and more), or a `logo` you supply.
They are not the vendors' artwork. Use the PlantUML libraries above when the official icons are
required.

## Related

- [UML (PlantUML)](uml.md) and [C4 (PlantUML)](c4plantuml.md)
- [D3 diagrams plugin](../plugins/d3.md)
- [Diagram types](index.md)
