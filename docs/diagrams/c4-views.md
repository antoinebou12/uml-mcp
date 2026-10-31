# C4 views in the MCP App

Use Kroki with `output_format: "svg"` for sharp labels in the viewer. The first
response carries bounded previews; selecting a view loads its full vector.
PNG and PDF are file exports. SVG is the default App preview. Source and
standalone HTML downloads are also available.

## Level 1: system context

Use `diagram_type: "c4plantuml"`:

```plantuml
@startuml
!include <C4/C4_Context>
Person(user, "User", "Uses the web application")
System(app, "Web application", "Frontend and backend")
System_Ext(payment, "Payment provider", "Processes payments")
Rel(user, app, "Uses", "HTTPS")
Rel(app, payment, "Charges", "HTTPS")
@enduml
```

## Level 2: containers

Use `diagram_type: "c4plantuml"`:

```plantuml
@startuml
!include <C4/C4_Container>
Person(user, "User")
System_Boundary(app, "Web application") {
  Container(web, "Frontend", "React", "Browser interface")
  Container(api, "Backend", "API", "Application services")
  ContainerDb(db, "Database", "PostgreSQL", "Application data")
}
Rel(user, web, "Uses", "HTTPS")
Rel(web, api, "Calls", "JSON / HTTPS")
Rel(api, db, "Reads and writes", "SQL")
@enduml
```

## Level 3: components

Use `diagram_type: "c4plantuml"`:

```plantuml
@startuml
!include <C4/C4_Component>
Container_Boundary(api, "Backend API") {
  Component(controller, "Request controller", "HTTP", "Validates requests")
  Component(service, "Order service", "Application", "Processes orders")
  Component(repo, "Order repository", "Persistence", "Stores orders")
}
Rel(controller, service, "Invokes")
Rel(service, repo, "Reads and writes")
@enduml
```

## Level 4: code

Use a normal UML class view, `diagram_type: "class"`. There is no separate
`C4_Code` library to include:

```plantuml
@startuml
class OrderController {
  +createOrder(request)
}
class OrderService {
  +placeOrder(order)
}
interface OrderRepository {
  +save(order)
}
OrderController --> OrderService
OrderService --> OrderRepository
@enduml
```

For a gallery, put these four sources in `generate_uml_batch.items`, with SVG
selected on each item. Keep `user_intent` outside the item renderer arguments.
Use a real PlantUML theme such as `plain`, `cerulean` or `cyborg`; `light` is a
background preference, not a PlantUML theme name. Leave the theme unset for
the standard C4 palette.
