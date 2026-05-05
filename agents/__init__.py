"""
agents/__init__.py
Central registry for the Digital Agent Workforce.
"""

# 1. Import registries from individual agent files
from .nexus import AGENT_REGISTRY as nexus_reg
from .nova import AGENT_REGISTRY as nova_reg

# 2. Merge them into the main AGENT_REGISTRY for app.py
AGENT_REGISTRY = {
    **nexus_reg,
    **nova_reg
}