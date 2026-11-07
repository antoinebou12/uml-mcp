---
name: c4_model
description: >-
  Writes valid c4_model JSON for uml-mcp (diagram_type=c4_model, bundled plugin c4). Use when the user asks for a C4 model to explore: system context, then containers, then components; then call validate_uml, then generate_uml_image (chat PNG) or generate_uml with output_format html (interactive MCP App page).
---

# c4_model diagram (uml-mcp plugin `c4`)

**`diagram_type`:** `c4_model`  
**Backend:** `plugin:c4` (bundled with uml-mcp, on by default)  
**Output formats:** html, svg

C4 model (context, containers, components) from one JSON model: static C4 diagram of a chosen level, or an interactive page that drills from systems into containers and components; html or svg

Load the workflow skill [uml-mcp-diagrams](../uml-mcp-diagrams/SKILL.md) and the focused guide `skill://uml-mcp-guides/c4-model/SKILL.md`. This file is notation only; it does not add an MCP tool.

## Example prompt

> C4 model of our e-commerce platform: shoppers, the storefront, order and payment services, Postgres, a Kafka topic, Stripe. Let me click into each level.

## Notation tips

- `people` (`id`, `name`, `description`, `external`) and `systems` (`id`, `name`, `description`, `external`, `containers`).
- A container: `id`, `name`, `technology`, `description`, `kind` (`app`, `web`, `db`, `queue`, `storage`, `function`), `service` (`aws:lambda`, `postgres`...) for its docs link, and `components` (`id`, `name`, `technology`, `description`).
- `relations` (`from`, `to`, `label`, `technology`, `async`) may join elements at any level; a relation between components shows as a line between their containers in the container view.
- Ids are unique across the whole model. `view` (`level`: `context`, `container`, `component`; `focus`: a system or container id) picks the level the SVG shows and the page opens on.
- Use `c4plantuml` instead when you need PlantUML C4 macros or a deployment view.

## Styling

Pass **`theme`** (`auto`, `dark` or `light`) to `generate_uml` / `generate_uml_image`, or set it in the source. `auto` follows the reader's system in the HTML page and is dark in static SVG and PNG.

## Example source

```json
{"title":"Internet banking system","description":"Customers view balances and make payments online","people":[{"id":"customer","name":"Personal Banking Customer","description":"A customer of the bank, with personal bank accounts"},{"id":"staff","name":"Back Office Staff","description":"Bank staff who handle customer support","external":false}],"systems":[{"id":"banking","name":"Internet Banking System","description":"Lets customers view their accounts and make payments","containers":[{"id":"web","name":"Web Application","technology":"Java and Spring MVC","kind":"app","description":"Delivers the static content and the single-page app"},{"id":"spa","name":"Single-Page App","technology":"TypeScript and React","kind":"web","service":"react","description":"All the internet banking features, in the browser"},{"id":"api","name":"API Application","technology":"Java and Spring Boot","kind":"app","description":"Internet banking features over a JSON/HTTPS API","components":[{"id":"signin","name":"Sign In Controller","technology":"Spring MVC Rest Controller","description":"Lets users sign in to the banking system"},{"id":"accounts","name":"Accounts Summary Controller","technology":"Spring MVC Rest Controller","description":"Lists a customer's accounts and balances"},{"id":"security","name":"Security Component","technology":"Spring Bean","description":"Signing in, changing passwords"},{"id":"facade","name":"Mainframe Banking Facade","technology":"Spring Bean","description":"A facade onto the mainframe banking system"},{"id":"notifier","name":"Notification Publisher","technology":"Spring Bean","description":"Publishes account events for e-mail delivery"}]},{"id":"events","name":"Account Events","technology":"Amazon SQS","kind":"queue","service":"aws:sqs","description":"Account changes waiting to be e-mailed"},{"id":"mailer","name":"Mail Sender","technology":"AWS Lambda","kind":"function","service":"aws:lambda","description":"Turns account events into e-mails"},{"id":"db","name":"Database","technology":"PostgreSQL","kind":"db","service":"postgres","description":"Users, hashed credentials and access logs"}]},{"id":"mainframe","name":"Mainframe Banking System","description":"Core banking: customers, accounts, transactions","external":true},{"id":"email","name":"E-mail System","description":"The internal Microsoft Exchange e-mail system","external":true}],"relations":[{"from":"customer","to":"web","label":"Visits","technology":"HTTPS"},{"from":"customer","to":"spa","label":"Views balances, makes payments"},{"from":"web","to":"spa","label":"Delivers to the browser"},{"from":"spa","to":"signin","label":"Signs in","technology":"JSON/HTTPS"},{"from":"spa","to":"accounts","label":"Reads accounts","technology":"JSON/HTTPS"},{"from":"signin","to":"security","label":"Uses"},{"from":"accounts","to":"facade","label":"Uses"},{"from":"security","to":"db","label":"Reads and writes","technology":"JDBC"},{"from":"facade","to":"mainframe","label":"Uses","technology":"XML/HTTPS"},{"from":"accounts","to":"notifier","label":"Uses"},{"from":"notifier","to":"events","label":"Publishes account events","technology":"SQS","async":true},{"from":"mailer","to":"events","label":"Polls","technology":"SQS","async":true},{"from":"mailer","to":"email","label":"Sends e-mail","technology":"SMTP"},{"from":"email","to":"customer","label":"Sends e-mails to"},{"from":"staff","to":"mainframe","label":"Uses"}]}
```
