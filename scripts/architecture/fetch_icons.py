#!/usr/bin/env python3
"""Fetch brand logos with a fallback chain, unmodified, for diagram builds.

Usage:
  python3 fetch_icons.py OUTDIR spec [spec ...]

Spec forms:
  name              -> slug == name          (e.g. hono)
  name:slug         -> different slug        (e.g. betterauth:better-auth)
  name=URL          -> explicit URL          (e.g. orpc=https://orpc.unnoq.com/logo.webp)
  name:aws/Service  -> official AWS icon     (e.g. lambda:aws/AWS-Lambda)
  name:gcp/Product  -> official Google Cloud icon (e.g. run:gcp/Cloud-Run)
  name:azure/Service -> official Azure icon  (e.g. vault:azure/Key-Vaults)

Sources tried in order:
  1. svgl              api.svgl.app?search={s} -> route (light variant when split)
  2. devicon           raw.githubusercontent.com/devicons/devicon/master/icons/{s}/{s}-original.svg
  3. gilbarbara/logos  cdn.jsdelivr.net/gh/gilbarbara/logos/logos/{s}-icon.svg then {s}.svg

simple-icons is deliberately not a source: its glyphs are monochrome redraws, not the
official marks. When every source misses, pass the official file as name=URL.

aws/ specs and the slugs aws, amazonwebservices and aws-* skip the chain and read AWS's own
package (aws.amazon.com/architecture/icons): gilbarbara's aws-* files keep an older color set.

gcp/ specs and the slugs gcp-* and google-cloud-* do the same with Google's packages
(cloud.google.com/icons). The slugs gcp and google-cloud are the Google Cloud mark, through the chain.

azure/ specs and the slugs azure, microsoft-azure and azure-* do the same with Microsoft's package
(learn.microsoft.com/azure/architecture/icons).

svgl is matched by normalized title equality (search is fuzzy — a loose match would
silently ship the wrong brand's logo, so non-exact hits fall through to next source).

Writes OUTDIR/<name>.<ext> and OUTDIR/manifest.json, plus OUTDIR/<name>_dark.<ext> when
the source has a dark-theme variant (for group labels). Flags white/near-white fills
(use a dark tile for those). Never modifies icon colors.
"""
import base64, functools, http.client, io, json, pathlib, re, sys, urllib.request, urllib.error, urllib.parse, zipfile

UA = {"User-Agent": "Mozilla/5.0 (stack-diagram-skill)"}
NAME_RE = re.compile(r"[A-Za-z0-9_-]+")   # becomes a filename and an %%ICON_<name>%% token
AWS_ICONS_PAGE = "https://aws.amazon.com/architecture/icons/"
AWS_PACKAGE_RE = re.compile(r"""(?:https:)?//[\w.-]+\.awsstatic\.com/[^"'\s]+/Icon-package_[^"'\s/]+\.zip""")
AWS_ICON_RE = re.compile(r"Architecture-Service-Icons_[^/]+/[^/]+/64/Arch_(.+)_64\.svg"
                         r"|Architecture-Group-Icons_[^/]+/(.+)_32\.svg"
                         r"|Resource-Icons_[^/]+/Res_General-Icons/Res_48_Light/Res_(.+)_48_Light\.svg")
AWS_ALIASES = {
    "s3": "Amazon-Simple-Storage-Service", "glacier": "Amazon-Simple-Storage-Service-Glacier",
    "sqs": "Amazon-Simple-Queue-Service", "sns": "Amazon-Simple-Notification-Service",
    "ses": "Amazon-Simple-Email-Service", "ecs": "Amazon-Elastic-Container-Service",
    "eks": "Amazon-Elastic-Kubernetes-Service", "ecr": "Amazon-Elastic-Container-Registry",
    "elb": "Elastic-Load-Balancing", "alb": "Elastic-Load-Balancing", "nlb": "Elastic-Load-Balancing",
    "iam": "AWS-Identity-and-Access-Management", "kms": "AWS-Key-Management-Service",
    "msk": "Amazon-Managed-Streaming-for-Apache-Kafka", "opensearch": "Amazon-OpenSearch-Service",
    "vpc": "Virtual-private-cloud-VPC",
}
GCP_PACKAGES = ("https://services.google.com/fh/files/misc/core-products-icons.zip",
                "https://services.google.com/fh/files/misc/category-icons.zip")
GCP_ICON_RE = re.compile(r"(?:Unique|Category) Icons/([^/]+)/SVG/[^/]+\.svg")
# Icon folder -> products, from Google's guide on cloud.google.com/icons; its bare "SQL" row is left out so gcp/sql is Cloud SQL
GCP_PRODUCTS = {
    "Agents": "AI Applications & Agents, AI Testing agent, Automotive AI agent, Code Documentation agent, "
              "Deep Research agent, Food ordering AI agent, Idea Generation agent, Customer Engagement Suite, "
              "Conversational Agents, Agent Assist, Conversational Insights, Contact Center as a Service",
    "AI _ Machine Learning": "AI and Machine Learning, Advanced Agent Modeling, AI Hub, AI Platform, "
              "AI Platform Unified, AutoML, AutoML Natural Language, AutoML Tables, AutoML Translation, "
              "AutoML Video Intelligence, AutoML Vision, Cloud GPU, Cloud Healthcare API, Cloud Natural Language API, "
              "Cloud Optimization AI, Cloud Optimization AI FleetRouting API, Cloud TPU, Cloud Translation API, "
              "Cloud Vision API, Data Labeling, Dialogflow ES, Document AI, Genomics, Healthcare NLP API, "
              "Media Translation API, Recommendations AI, Speech to Text, Tensorflow Enterprise, Text To Speech, "
              "Visual Inspection AI",
    "Collaboration": "Google Workspace",
    "Compute": "Batch, Container Optimized OS, GCE Systems Management, Migrate To Virtual Machines, "
               "OS Config Management, OS Inventory Management, OS Patch Management, VMware Engine",
    "Containers": "Backup for GKE, Knative serving, Migrate To Containers",
    "Data Analytics": "Analytics Hub, BigLake, Cloud Composer, Cloud Data Fusion, Data Catalog, Data Layers, "
                      "Data Loss Prevention API, Dataflow, Dataplex, Datapol, Dataprep, Dataproc, Dataproc Metastore, "
                      "Datashare, Datastream, Pub/Sub",
    "Databases": "Bare Metal Solution, Bigtable, Database Center, Database Migration Service, Datastore, Firestore, "
                 "Memorystore",
    "Developer Tools": "Cloud Code, Cloud Deployment Manager, Cloud Scheduler, Cloud Shell, Cloud Tasks, "
                       "Cloud Workstations, Runtime Config, Service Catalog, Tools For Powershell",
    "DevOps": "Artifact Registry, Cloud Build, Cloud Deploy, Container Registry",
    "Hybrid & Multicloud": "Hybrid and Multicloud",
    "Integration Services": "Advanced API Security, API Analytics, Application Integration, Cloud API Gateway, "
                            "Cloud APIs, Cloud Endpoints, Connectors, Developer Portal, Eventarc, Workflows",
    "Management Tools": "Carbon Footprint, Producer Portal",
    "Maps & Geospatial": "Maps and Geospatial, Earth Engine, Google Earth, Google Maps Platform",
    "Marketplace": "Google Cloud Marketplace",
    "Migration": "Migrate For Compute Engine, Transfer Appliance",
    "Networking": "Cloud Armor, Cloud CDN, Cloud DNS, Cloud Domains, Cloud Firewall Rules, Cloud IDS, "
                  "Cloud Interconnect, Cloud Load Balancing, Load Balancer, Cloud NAT, Cloud Network, Cloud Router, "
                  "Cloud VPN, Connectivity Test, Data Transfer, Network Connectivity Center, "
                  "Network Intelligence Center, Network Security, Network Tiers, Network Topology, Packet Mirroring, "
                  "Partner Interconnect, Premium Network Tier, Private Connectivity, Private Service Connect, Routes, "
                  "Service Mesh, Virtual Private Cloud, VPC",
    "Observability": "Cloud Audit Logs, Cloud Logging, Cloud Monitoring, Error Reporting, "
                     "Google Cloud Observability, Profiler, Trace",
    "Operations": "App Hub, Backup and DR, Capacity Planner, Performance Dashboard, Personalized Service Health",
    "Security Identity": "Security and Identity, Access Context Manager, Asset Inventory, Assured Workloads, "
                         "BeyondCorp, Binary Authorization, Certificate Authority Service, Certificate Manager, "
                         "Cloud Asset Inventory, Cloud External Key Manager, Cloud HSM, Cloud Security Scanner, "
                         "Identity and Access Management, IAM, Identity Aware Proxy, IAP, Identity Platform, "
                         "Key Access Justifications, Key Management Service, KMS, "
                         "Managed Service For Microsoft Active Directory, Phishing Protection, Policy Analyzer, "
                         "Recaptcha Enterprise, Risk Manager, Secret Manager, Security Key Enforcement, Web Risk, "
                         "Web Security Scanner, Workload Identity Federation",
    "Serverless Computing": "Serverless, App Engine, Cloud Functions, Cloud Run functions",
    "Storage": "Filestore, Google Cloud NetApp Volumes, Local SSD, Parallelstore, Storage Transfer Service",
    "Web & Mobile": "Web and Mobile",
    "Web3": "Blockchain Node Engine, Blockchain RPC",
    "AlloyDB": "AlloyDB Omni",
    "BigQuery": "BigQuery Functions, BigQuery Omni",
    "Cloud Spanner": "Spanner",
    "Cloud Storage": "GCS",
    "Compute Engine": "GCE",
    "Distributed Cloud": "Google Distributed Cloud",
    "GKE": "Google Kubernetes Engine, Kubernetes Engine",
    "Hyperdisk": "Persistent Disk",
    "Looker": "Looker Studio, Looker Studio Pro",
    "Security Operations": "Google Security Operations, SecOps",
    "Threat Intelligence": "Google Threat Intelligence",
}
AZURE_ICONS_PAGE = "https://learn.microsoft.com/en-us/azure/architecture/icons/"
AZURE_PACKAGE_RE = re.compile(r"https://arch-center\.azureedge\.net/icons/Azure_Public_Service_Icons_V\d+\.zip")
AZURE_ICON_RE = re.compile(r"Azure_Public_Service_Icons/Icons/[^/]+/\d+\s*-icon-service-(.+)\.svg")
AZURE_ALIASES = {
    "webapp": "App-Services", "functions": "Function-Apps", "azurefunctions": "Function-Apps",
    "aks": "Kubernetes-Services", "vm": "Virtual-Machine", "vmss": "VM-Scale-Sets",
    "containerapp": "Container-Apps-Environments", "containerapps": "Container-Apps-Environments",
    "acr": "Container-Registries", "aci": "Container-Instances", "staticwebapp": "Static-Apps",
    "staticwebapps": "Static-Apps", "frontdoor": "Front-Door-and-CDN-Profiles",
    "appgateway": "Application-Gateways", "lb": "Load-Balancers", "vnet": "Virtual-Networks",
    "nsg": "Network-Security-Groups", "waf": "Web-Application-Firewall-Policies(WAF)", "dns": "DNS-Zones",
    "expressroute": "ExpressRoute-Circuits", "trafficmanager": "Traffic-Manager-Profiles",
    "vpngateway": "Virtual-Network-Gateways", "storage": "Storage-Accounts", "blob": "Storage-Accounts",
    "blobstorage": "Storage-Accounts", "cosmos": "Azure-Cosmos-DB", "redis": "Azure-Managed-Redis",
    "managedredis": "Azure-Managed-Redis", "postgres": "Azure-Database-PostgreSQL-Server",
    "postgresql": "Azure-Database-PostgreSQL-Server", "mysql": "Azure-Database-MySQL-Server",
    "eventgrid": "Event-Grid-Topics", "apim": "API-Management-Services", "apimanagement": "API-Management-Services",
    "foundry": "AI-Foundry", "aisearch": "Cognitive-Search", "search": "Cognitive-Search",
    "appinsights": "Application-Insights", "loganalytics": "Log-Analytics-Workspaces",
    "datafactory": "Data-Factories", "synapse": "Azure-Synapse-Analytics", "resourcegroup": "Resource-Groups",
    "rg": "Resource-Groups", "managedidentity": "Managed-Identities",
}
PACKAGES = {}

def get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def read(url):
    """Bytes of url; '<package URL>#<member>' reads from the already-downloaded zip."""
    zip_url, _, member = url.partition("#")
    return PACKAGES[zip_url].read(member) if zip_url in PACKAGES else get(url)

def package_from_page(page, link_re):
    """Download the zip a page links to, which changes with each release, and return its URL.
    It is read once per run and stays in memory."""
    link = link_re.search(get(page).decode("utf-8", "ignore"))
    if not link:
        raise OSError(f"no icon package link on {page}")
    url = urllib.parse.urljoin(page, link.group())
    PACKAGES[url] = zipfile.ZipFile(io.BytesIO(get(url)))
    return url

def looks_svg(b): return b.lstrip()[:200].lstrip().startswith((b"<svg", b"<?xml", b"<!DOC"))
def ext_of(b, url):
    if looks_svg(b): return "svg"
    if b[:8] == b"\x89PNG\r\n\x1a\n": return "png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP": return "webp"
    m = re.search(r"\.(png|webp|jpe?g|svg)(\?|$)", url)
    return m.group(1) if m else None

def white_fill(b):
    """True only when the mark is white overall: at least one white paint and no
    non-white paint anywhere (a white detail on a colored logo is not a white logo)."""
    if not looks_svg(b): return False
    s = b.decode("utf-8", "ignore")
    paints = re.findall(r'(?:fill|stroke|stop-color)[=:]\s*"?([#a-zA-Z][^";\s>]*)', s)
    white = colored = False
    for p in paints:
        p = p.strip().lower()
        if p in ("none", "transparent", "currentcolor") or p.startswith("url("):
            continue
        if re.fullmatch(r"#f{3}(f{3})?|white", p): white = True
        else: colored = True
    return white and not colored

def norm(s): return re.sub(r"[^a-z0-9]", "", s.lower())

def svgl_lookup(slug):
    """Exact-normalized-title match on svgl's search API: (url, dark_url or None), or
    None if no exact hit. svgl's search matches title substrings ('better-auth' misses
    'Better Auth', 'nextjs' misses 'Next.js'), so also try the slug with separators
    turned into spaces and without a trailing 'js' (svgl titles Vue 'Vue', not 'Vue.js')."""
    queries = [slug, re.sub(r"[-_.]+", " ", slug).strip()]
    targets = {norm(slug)}
    if len(slug) > 4 and slug.endswith("js"):
        queries.append(slug[:-2]); targets.add(norm(slug[:-2]))
    for q in dict.fromkeys(queries):
        try:
            items = json.loads(get(f"https://api.svgl.app?search={urllib.parse.quote(q)}"))
        except Exception:
            continue
        for it in items if isinstance(items, list) else []:
            if norm(it.get("title", "")) in targets:
                route = it.get("route")
                if isinstance(route, dict):    # light/dark split: tiles are white -> light
                    light, dark = route.get("light"), route.get("dark")
                    return (light, dark) if light else (dark, None)
                return route, None
    return None

@functools.lru_cache(maxsize=1)
def aws_index():
    """AWS's icon package as {normalized name: (name, url, dark url or None)}."""
    url = package_from_page(AWS_ICONS_PAGE, AWS_PACKAGE_RE)
    files = set(PACKAGES[url].namelist())
    index = {}
    for f in sorted(files):
        m = AWS_ICON_RE.fullmatch(f)
        if m:
            # the General- prefix keeps General-Shield from taking the short name of AWS-Shield
            name = m.group(1) or m.group(2) or f"General-{m.group(3)}"
            dark = f.replace("_Light", "_Dark") if m.group(3) else f[:-4] + "_Dark.svg"
            index.setdefault(norm(name), (name, f"{url}#{f}", f"{url}#{dark}" if dark in files else None))
    return index

def aws_sources(query):
    """Exact match on the package's names or an acronym, with the AWS-/Amazon- prefix optional.
    A miss lists every name: a partial match could ship the wrong service's icon."""
    try:
        index = aws_index()
    except (OSError, zipfile.BadZipFile, http.client.HTTPException) as e:
        print(f"AWS  icon package unavailable: {e}")
        return []
    q = norm(AWS_ALIASES.get(norm(query), query))
    hit = index.get(q) or next((v for k, v in index.items() if re.sub(r"^(aws|amazon)", "", k) == q), None)
    if hit:
        return [("aws", hit[1], hit[2])]
    print(f"AWS  {query!r} is not a name in the package. Names: {', '.join(sorted(v[0] for v in index.values()))}")
    return []

@functools.lru_cache(maxsize=1)
def gcp_index():
    """Google's core and category icons as {normalized folder name: (folder name, url)}."""
    index = {}
    for url in GCP_PACKAGES:
        PACKAGES[url] = zipfile.ZipFile(io.BytesIO(get(url)))
        for f in PACKAGES[url].namelist():
            m = GCP_ICON_RE.fullmatch(f)
            if m:
                index[norm(m.group(1))] = (m.group(1), f"{url}#{f}")
    return index

def gcp_sources(query):
    """Exact match on a product or icon name, with the Cloud/Google prefix optional. Most products
    share their category's icon. A miss lists every name, as for AWS."""
    try:
        index = gcp_index()
    except (OSError, zipfile.BadZipFile, http.client.HTTPException) as e:
        print(f"GCP  icon packages unavailable: {e}")
        return []
    products = {p: icon for icon, names in GCP_PRODUCTS.items() for p in names.split(", ")}
    targets = {k: k for k in index} | {norm(p): norm(icon) for p, icon in products.items()}
    q = norm(query)
    hit = index.get(targets.get(q) or next((v for k, v in targets.items() if re.sub(r"^(google|cloud)+", "", k) == q), None))
    if hit:
        return [("gcp", hit[1], None)]
    names = sorted({v[0] for v in index.values()} | set(products), key=str.lower)
    print(f"GCP  {query!r} is not a product or icon name. Names: {', '.join(names)}")
    return []

@functools.lru_cache(maxsize=1)
def azure_index():
    """Microsoft's icon package as {normalized name: (name, url)}. A name can sit in several folders."""
    url = package_from_page(AZURE_ICONS_PAGE, AZURE_PACKAGE_RE)
    index = {}
    for f in sorted(PACKAGES[url].namelist()):
        m = AZURE_ICON_RE.fullmatch(f)
        if m:
            index.setdefault(norm(m.group(1)), (m.group(1).strip(), f"{url}#{f}"))
    return index

def azure_sources(query):
    """Exact match on the package's names or a short form, with the Azure-/Microsoft- prefix and a
    plural s optional. A miss lists every name, as for AWS."""
    try:
        index = azure_index()
    except (OSError, zipfile.BadZipFile, http.client.HTTPException) as e:
        print(f"Azure icon package unavailable: {e}")
        return []
    q = norm(AZURE_ALIASES.get(norm(query), query))
    short = lambda s: re.sub(r"^(azure|microsoft)|s$", "", s)
    hit = index.get(q) or next((v for k, v in index.items() if short(k) == short(q)), None)
    if hit:
        return [("azure", hit[1], None)]
    print(f"Azure {query!r} is not a name in the package. Names: {', '.join(sorted(v[0] for v in index.values()))}")
    return []

def sources(slug):
    # concept icons: slug "lucide/<icon-name>" -> Lucide line icon (browse: lucide.dev/icons)
    if slug.startswith("lucide/"):
        return [("lucide", f"https://cdn.jsdelivr.net/npm/lucide-static/icons/{slug[7:]}.svg", None)]
    if slug.startswith("aws/"):
        return aws_sources(slug[4:])
    if norm(slug) in ("aws", "amazonwebservices"):
        return aws_sources("AWS-Cloud-logo")
    if slug[:4].lower() == "aws-":
        return aws_sources(slug[4:])
    if norm(slug) in ("azure", "microsoftazure"):
        return azure_sources("Azure-A")
    azure = re.fullmatch(r"azure[/-](.+)", slug, re.IGNORECASE)
    if azure:
        return azure_sources(azure.group(1))
    if norm(slug) in ("gcp", "googlecloudplatform"):
        slug = "google-cloud"
    gcp = re.fullmatch(r"(?:gcp/|gcp-|google-cloud-)(.+)", slug, re.IGNORECASE)
    if gcp:
        return gcp_sources(gcp.group(1))
    out = []
    svgl = svgl_lookup(slug)
    if svgl:
        out.append(("svgl", *svgl))
    return out + [
        ("devicon", f"https://raw.githubusercontent.com/devicons/devicon/master/icons/{slug}/{slug}-original.svg", None),
        ("gilbarbara", f"https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/{slug}-icon.svg", None),
        ("gilbarbara", f"https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/{slug}.svg", None),
    ]

def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    outdir = pathlib.Path(sys.argv[1]); outdir.mkdir(parents=True, exist_ok=True)
    mpath = outdir / "manifest.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {}   # merge across runs
    failed = []
    bad_names = False
    for spec in sys.argv[2:]:
        if "=" in spec:
            name, url = spec.split("=", 1); tries = [("explicit", url, None)]
        elif ":" in spec:
            name, slug = spec.split(":", 1); tries = sources(slug)
        else:
            name = spec; tries = sources(name.lower().replace(" ", ""))
        if not NAME_RE.fullmatch(name):
            print(f"SKIP {name!r}: icon name must match [A-Za-z0-9_-]+ (it becomes a filename)")
            bad_names = True; continue
        got = None
        for src, url, dark_url in tries:
            try:
                b = read(url)
            except (urllib.error.URLError, urllib.error.HTTPError, OSError):
                continue
            ext = ext_of(b, url)
            if not ext or len(b) < 50:      # 404 pages, empty bodies
                continue
            got = (src, url, dark_url, b, ext); break
        if not got:
            failed.append(name); continue
        src, url, dark_url, b, ext = got
        if src == "lucide":
            # concept icon, not a brand logo — tinting it to the diagram's slate ink is fine
            b = b.replace(b'stroke="currentColor"', b'stroke="#3d4660"')
            b = b.replace(b'stroke-width="2"', b'stroke-width="1.7"')
        # build.py embeds whichever <name>.* sorts first, so a re-fetch must not leave the old file
        for old in [*outdir.glob(f"{name}.*"), *outdir.glob(f"{name}_dark.*")]:
            if old != mpath:
                old.unlink()
        path = outdir / f"{name}.{ext}"
        path.write_bytes(b)
        entry = {"source": src, "url": url, "file": path.name, "bytes": len(b)}
        if white_fill(b):
            entry["white_fill"] = True
            entry["note"] = ("white fill detected — MAY be a false positive (an inner detail on a "
                             "colored logo). Inspect the SVG; only use a dark tile if the mark is "
                             "actually white overall. Never recolor.")
        if dark_url:
            try:
                db = read(dark_url)
            except (urllib.error.URLError, urllib.error.HTTPError, OSError):
                db = b""
            dext = ext_of(db, dark_url) if len(db) >= 50 else None
            if dext:
                dpath = outdir / f"{name}_dark.{dext}"
                dpath.write_bytes(db); entry["dark_file"] = dpath.name; entry["dark_url"] = dark_url
        manifest[name] = entry
        flag = " [WHITE FILL -> dark tile]" if entry.get("white_fill") else ""
        if "dark_file" in entry:
            flag += f" +{entry['dark_file']} (dark-theme group label)"
        print(f"OK   {name:<16} {src:<12} {len(b):>7}B .{ext}{flag}")
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    for name in failed:
        print(f"FAIL {name:<16} no source has it — try name:otherslug, or name=URL with the official "
              f"file (the project's repo root/docs/assets, or its site's /logo.svg, /favicon.svg)")
    sys.exit(1 if failed or bad_names else 0)

if __name__ == "__main__":
    main()
