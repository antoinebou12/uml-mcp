# UML-MCP: A Diagram Generation Server with MCP Interface

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![smithery badge](https://smithery.ai/badge/@antoinebou12/uml)](https://smithery.ai/server/@antoinebou12/uml)

UML-MCP is a powerful diagram generation server that implements the Model Context Protocol (MCP), enabling seamless diagram creation directly from AI assistants and other applications. 

## 🌟 Features

- **Multiple Diagram Types**: Support for UML diagrams (Class, Sequence, Activity, etc.), Mermaid, D2, and more
- **MCP Integration**: Seamless integration with LLM assistants supporting the Model Context Protocol
- **Playground Links**: Direct links to online editors for each diagram type
- **Multiple Output Formats**: SVG, PNG, PDF, and other format options
- **Easy Configuration**: Works with local and remote diagram rendering services

## 📋 Supported Diagram Types

UML-MCP supports a wide variety of diagram types:

| Category | Diagram Types |
|----------|---------------|
| UML | Class, Sequence, Activity, Use Case, State, Component, Deployment, Object |
| Other | Mermaid, D2, Graphviz, ERD, BlockDiag, BPMN, C4 with PlantUML |

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- pip (Python package installer)

### Installation

### Installing via Smithery

To install UML Model Context Protocol for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@antoinebou12/uml):

```bash
npx -y @smithery/cli install @antoinebou12/uml --client claude
```

### Manual Installation
1. Clone the repository:

```bash
git clone https://github.com/yourusername/uml-mcp.git
cd uml-mcp
```

2. Install the dependencies:

```bash
pip install -r requirements.txt
```

3. For development environments:

```bash
pip install -r requirements-dev.txt
```

### Running the Server

Start the MCP server:

```bash
python mcp_server.py
```

This will start the server using stdio for communication with MCP clients.

## 🔧 Configuration

### Editor Integration

#### Cursor

To integrate with Cursor:

```bash
python mcp/install_to_cursor.py
```

Or manually configure in Cursor settings:

```json
"mcpServers": {
  "UML-MCP-Server": {
    "command": "python",
    "args": ["/path/to/uml-mcp/mcp_server.py"],
    "output_dir": "/path/to/output"
  }
}
```

### Environment Variables

- `MCP_OUTPUT_DIR` - Directory to save generated diagrams (default: `./output`)
- `KROKI_SERVER` - URL of the Kroki server (default: `https://kroki.io`)
- `PLANTUML_SERVER` - URL of the PlantUML server (default: `http://plantuml-server:8080`)
- `USE_LOCAL_KROKI` - Use local Kroki server (true/false)
- `USE_LOCAL_PLANTUML` - Use local PlantUML server (true/false)

## 📚 Documentation

For detailed documentation, visit the [docs](./docs) directory or our [documentation site](https://uml-mcp.readthedocs.io/).

## 🧩 Architecture

UML-MCP is built with a modular architecture:

- **MCP Server Core**: Handles MCP protocol communication
- **Diagram Generators**: Supporting different diagram types
- **Tools**: Expose diagram generation functionality through MCP
- **Resources**: Provide templates and examples for various diagram types

## 🛠️ Local Development

For local development:

1. Set up local PlantUML and/or Kroki servers:

```bash
# PlantUML
docker run -d -p 8080:8080 plantuml/plantuml-server

# Kroki
docker run -d -p 8000:8000 yuzutech/kroki
```

2. Configure environment variables:

```bash
export USE_LOCAL_PLANTUML=true
export PLANTUML_SERVER=http://localhost:8080
export USE_LOCAL_KROKI=true  
export KROKI_SERVER=http://localhost:8000
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👏 Acknowledgements

- [PlantUML](https://plantuml.com/) - UML diagram generation
- [Kroki](https://kroki.io/) - Unified diagram generation service
- [Mermaid](https://mermaid.js.org/) - Generation of diagrams from text
- [D2](https://d2lang.com/) - Modern diagram scripting language
