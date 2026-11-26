"""The shared part of Goldilocks Workbench (D1).

It holds what the forms share: the tool registry and modules, the model layer, the server kit, the store and the
goldilocks-dft client. It never imports goldilocks_chat, goldilocks_agent, Deep Agents, AiiDA or MLIP packages
(tools/checks/import_boundary.py).
"""
