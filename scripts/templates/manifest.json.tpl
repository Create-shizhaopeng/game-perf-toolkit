{
  "name": "{{module_name}}",
  "display_name": "{{display_name}}",
  "version": "0.1.0",
  "description": "",
  "author": "",
  "python_requires": ">=3.12",
  "entry": "src.plugin",
  "service_entry": "src.service",
  "dependencies": {
    "toolkit_modules": [],
    "python_packages": []
  },
  "provides": {
    "gui": true,
    "cli": true,
    "agent_tools": false,
    "workflow_stages": []
  },
  "cli_namespace": "{{cli_namespace}}",
  "events": {
    "emits": [],
    "listens": []
  },
  "database": {
    "migrations": "src/migrations/",
    "tables": []
  },
  "external_tools": []
}
