# agents package
from agents.nova       import NovaAgent
from agents.axiom      import AxiomAgent
from agents.nexus      import NexusAgent
from agents.prometheus import PrometheusAgent
from agents.sentinel   import SentinelAgent

AGENT_REGISTRY = {
    "NOVA":       NovaAgent(),
    "AXIOM":      AxiomAgent(),
    "NEXUS":      NexusAgent(),
    "PROMETHEUS": PrometheusAgent(),
    "SENTINEL":   SentinelAgent(),
}
