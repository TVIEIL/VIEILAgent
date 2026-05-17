import os
from dotenv import load_dotenv

load_dotenv()
import autogpt.sdk.forge_log

autogpt.sdk.forge_log.setup_logger()
LOG = autogpt.sdk.forge_log.ForgeLogger(__name__)

# On importe les routes APÈS avoir configuré les variables d'environnement
from autogpt.sdk.routes.agent_protocol import base_router as router

if __name__ == "__main__":
    """Runs the agent server"""

    import autogpt.agent
    import autogpt.sdk.db
    from autogpt.sdk.workspace import LocalWorkspace

    database_name = os.getenv("DATABASE_STRING")
    workspace = LocalWorkspace(os.getenv("AGENT_WORKSPACE"))
    port = os.getenv("PORT")

    database = autogpt.sdk.db.AgentDB(database_name, debug_enabled=True)
    
    # On instancie bien ton agent personnalisé
    agent = autogpt.agent.AutoGPTAgent(database=database, workspace=workspace)

    # LE LIEN DIRECT : On s'assure que le routeur utilise explicitement TON agent
    router.agent = agent

    agent.start(port=port, router=router)
