workspace "Example" "Description" {
    model {
        user = person "User"
        app = softwareSystem "App" "A sample system"
        user -> app "Uses"
    }
    views {
        systemContext app "Context" {
            include *
        }
    }
}