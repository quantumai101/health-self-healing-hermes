"""
agents/__init__.py
Central registry for the Digital Agent Workforce.
"""
from .nexus import AGENT_REGISTRY as nexus_reg
from .nova import AGENT_REGISTRY as nova_reg
from .axiom import AxiomAgent
from .prometheus import PrometheusAgent
from .sentinel import SentinelAgent

AGENT_REGISTRY = {
    **nexus_reg,
    **nova_reg,
    "AXIOM":      AxiomAgent,
    "PROMETHEUS": PrometheusAgent,
    "SENTINEL":   SentinelAgent,
}
